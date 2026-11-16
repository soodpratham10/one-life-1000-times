Attribute VB_Name = "OneLifeCheck"
' One Life, 1,000 Times: independent VBA rebuild of the risk engine (Phase 4).
'
' Rebuilt from the assumptions register (docs/assumptions.md: A04, A07, A08,
' A18, A19, A26, A27) using only the data sheets in this workbook (Data_q,
' Data_hr, Data_prev, Data_former). Plain VBA: no Scripting.Dictionary or other
' Windows-only libraries, so it runs in Excel for Mac and Windows.
' 2017-2019 death rates, no future improvement.
'
' Macros:
'   CheckAllCases  every value in the Reference sheet, worked out again and compared -> Summary
'   RunCase        one person (name in Results!B1), age by age, with Python's values -> Results

Option Explicit

Private Const MAX_AGE As Long = 110
Private Const CAP_LOW As Double = 0.35
Private Const CAP_HIGH As Double = 5#
Private Const TAPER_START As Long = 79
Private Const GRAMS_PER_DRINK As Double = 13.45
Private Const QUIT_RATE As Double = 0.05
Private Const QUIT_FROM_AGE As Long = 25
Private Const TOLERANCE As Double = 0.000000001

Private Type Person
    Sex As String
    Age As Long
    Region As String
    Smoking As String
    QuitAge As Long
    Keeps As Boolean
    Minutes As Double
    HeightCm As Double
    WeightKg As Double
    Drinks As Double
    FruitVeg As Double
End Type

Private QData As Variant
Private HRData As Variant
Private PrevData As Variant
Private FormerData As Variant
Private RefData As Variant

' ---------------------------------------------------------------- data

Private Sub LoadData()
    QData = ThisWorkbook.Worksheets("Data_q").Range("A1").CurrentRegion.Value
    HRData = ThisWorkbook.Worksheets("Data_hr").Range("A1").CurrentRegion.Value
    PrevData = ThisWorkbook.Worksheets("Data_prev").Range("A1").CurrentRegion.Value
    FormerData = ThisWorkbook.Worksheets("Data_former").Range("A1").CurrentRegion.Value
    RefData = ThisWorkbook.Worksheets("Reference").Range("A1").CurrentRegion.Value
End Sub

Private Function ColumnOf(data As Variant, header As String) As Long
    Dim j As Long
    For j = 1 To UBound(data, 2)
        If CStr(data(1, j)) = header Then
            ColumnOf = j
            Exit Function
        End If
    Next j
    Err.Raise vbObjectError + 1, , "No column " & header
End Function

Private Function BaseQ(region As String, sex As String, age As Long) As Double
    ' Data_q: column "age", then one column per region and sex; row 2 is age 0
    BaseQ = QData(age + 2, ColumnOf(QData, region & "_" & sex))
End Function

Private Function Hazard(factor As String, level As String, sex As String) As Double
    Dim pass As Long, i As Long, want As String
    For pass = 1 To 2
        If pass = 1 Then want = sex Else want = "B"
        For i = 2 To UBound(HRData, 1)
            If HRData(i, 1) = factor And HRData(i, 2) = level And HRData(i, 3) = want Then
                Hazard = HRData(i, 4)
                Exit Function
            End If
        Next i
    Next pass
    Err.Raise vbObjectError + 2, , "No hazard ratio for " & factor & " " & level & " " & sex
End Function

Private Function Taper(age As Long) As Double
    If age <= TAPER_START Then
        Taper = 1#
    Else
        Taper = (MAX_AGE - age) / (MAX_AGE - TAPER_START)
        If Taper < 0 Then Taper = 0#
    End If
End Function

Private Function GroupLo(age As Long) As Long
    If age <= 34 Then
        GroupLo = 18
    ElseIf age <= 49 Then
        GroupLo = 35
    ElseIf age <= 64 Then
        GroupLo = 50
    Else
        GroupLo = 65
    End If
End Function

Private Function Pct(sex As String, lo As Long, indicator As String) As Double
    Dim i As Long
    For i = 2 To UBound(PrevData, 1)
        If PrevData(i, 1) = sex And PrevData(i, 2) = lo And PrevData(i, 4) = indicator Then
            Pct = PrevData(i, 5) / 100
            Exit Function
        End If
    Next i
    Err.Raise vbObjectError + 3, , "No CCHS figure for " & indicator & " " & sex & " " & lo
End Function

Private Function FormerShare(sex As String, lo As Long) As Double
    Dim i As Long
    For i = 2 To UBound(FormerData, 1)
        If FormerData(i, 1) = sex And FormerData(i, 2) = lo Then
            FormerShare = FormerData(i, 4) / 100
            Exit Function
        End If
    Next i
    Err.Raise vbObjectError + 4, , "No former-smoker share for " & sex & " " & lo
End Function

' ---------------------------------------------------------------- population mix (A18, A19)

Private Sub Mix(sex As String, lo As Long, factor As String, levels() As String, shares() As Double)
    Dim cur As Double, frm As Double, act As Double, ovr As Double, obs As Double, five As Double
    Select Case factor
    Case "smoking"
        cur = Pct(sex, lo, "current_smoker")
        frm = FormerShare(sex, lo)
        If lo < 50 Then
            ReDim levels(1 To 4): ReDim shares(1 To 4)
            levels(1) = "never": shares(1) = 1 - cur - frm
            levels(2) = "current": shares(2) = cur
            levels(3) = "quit_before_35": shares(3) = frm * 0.75
            levels(4) = "quit_35_44": shares(4) = frm * 0.25
        Else
            ReDim levels(1 To 6): ReDim shares(1 To 6)
            levels(1) = "never": shares(1) = 1 - cur - frm
            levels(2) = "current": shares(2) = cur
            levels(3) = "quit_before_35": shares(3) = frm * 0.4
            levels(4) = "quit_35_44": shares(4) = frm * 0.3
            levels(5) = "quit_45_54": shares(5) = frm * 0.2
            levels(6) = "quit_55_plus": shares(6) = frm * 0.1
        End If
    Case "activity"
        act = Pct(sex, lo, "active_150")
        ReDim levels(1 To 5): ReDim shares(1 To 5)
        levels(1) = "none": shares(1) = (1 - act) * 0.5
        levels(2) = "under_150": shares(2) = (1 - act) * 0.5
        levels(3) = "150_299": shares(3) = act * 0.5
        levels(4) = "300_449": shares(4) = act * 0.25
        levels(5) = "450_plus": shares(5) = act * 0.25
    Case "bmi"
        ovr = Pct(sex, lo, "overweight")
        obs = Pct(sex, lo, "obese")
        ReDim levels(1 To 6): ReDim shares(1 To 6)
        levels(1) = "18.5_25": shares(1) = 1 - ovr - obs
        levels(2) = "25_27.5": shares(2) = ovr * 0.5
        levels(3) = "27.5_30": shares(3) = ovr * 0.5
        levels(4) = "30_35": shares(4) = obs * (15.2 / 23#)
        levels(5) = "35_40": shares(5) = obs * (5.1 / 23#)
        levels(6) = "40_plus": shares(6) = obs * (2.7 / 23#)
    Case "alcohol"
        ReDim levels(1 To 1): ReDim shares(1 To 1)
        levels(1) = "under_25g": shares(1) = 1#
    Case "fruit_veg"
        five = Pct(sex, lo, "fruit_veg_5")
        ReDim levels(1 To 2): ReDim shares(1 To 2)
        levels(1) = "0_2": shares(1) = 1 - five
        levels(2) = "5_plus": shares(2) = five
    End Select
End Sub

Private Function AverageMultiplier(sex As String, age As Long) As Double
    Dim factors As Variant, f As Variant, levels() As String, shares() As Double
    Dim w As Double, total As Double, s As Double, k As Long
    factors = Array("smoking", "activity", "bmi", "alcohol", "fruit_veg")
    w = Taper(age)
    total = 1#
    For Each f In factors
        Mix sex, GroupLo(age), CStr(f), levels, shares
        s = 0#
        For k = LBound(levels) To UBound(levels)
            s = s + shares(k) * Hazard(CStr(f), levels(k), sex) ^ w
        Next k
        total = total * s
    Next f
    AverageMultiplier = total
End Function

' ---------------------------------------------------------------- a person's levels

Private Function QuitLevel(quitAge As Long) As String
    If quitAge < 35 Then
        QuitLevel = "quit_before_35"
    ElseIf quitAge < 45 Then
        QuitLevel = "quit_35_44"
    ElseIf quitAge < 55 Then
        QuitLevel = "quit_45_54"
    Else
        QuitLevel = "quit_55_plus"
    End If
End Function

Private Function LevelOf(p As Person, factor As String) As String
    Dim m As Double, b As Double, g As Double, f As Double
    Select Case factor
    Case "smoking"
        If p.Smoking = "former" Then LevelOf = QuitLevel(p.QuitAge) Else LevelOf = p.Smoking
    Case "activity"
        m = p.Minutes
        If m = 0 Then
            LevelOf = "none"
        ElseIf m < 150 Then
            LevelOf = "under_150"
        ElseIf m < 300 Then
            LevelOf = "150_299"
        ElseIf m < 450 Then
            LevelOf = "300_449"
        Else
            LevelOf = "450_plus"
        End If
    Case "bmi"
        b = p.WeightKg / (p.HeightCm / 100) ^ 2
        If b < 18.5 Then
            LevelOf = "under_18.5"
        ElseIf b < 25 Then
            LevelOf = "18.5_25"
        ElseIf b < 27.5 Then
            LevelOf = "25_27.5"
        ElseIf b < 30 Then
            LevelOf = "27.5_30"
        ElseIf b < 35 Then
            LevelOf = "30_35"
        ElseIf b < 40 Then
            LevelOf = "35_40"
        Else
            LevelOf = "40_plus"
        End If
    Case "alcohol"
        g = p.Drinks * GRAMS_PER_DRINK / 7
        If g < 25 Then
            LevelOf = "under_25g"
        ElseIf g < 45 Then
            LevelOf = "25_44g"
        ElseIf g < 65 Then
            LevelOf = "45_64g"
        Else
            LevelOf = "65g_plus"
        End If
    Case "fruit_veg"
        f = p.FruitVeg
        If f < 3 Then
            LevelOf = "0_2"
        ElseIf f < 4 Then
            LevelOf = "3"
        ElseIf f < 5 Then
            LevelOf = "4"
        Else
            LevelOf = "5_plus"
        End If
    End Select
End Function

' ---------------------------------------------------------------- habits that change with age (A26)

Private Sub Slice(sex As String, lo As Long, factor As String, level As String, a As Double, b As Double)
    ' the level's slice [a, b) of the cumulative distribution, levels taken in order of the answer
    Dim levels() As String, shares() As Double, k As Long, cum As Double
    Mix sex, lo, factor, levels, shares
    cum = 0#
    a = -1#: b = -1#
    For k = LBound(levels) To UBound(levels)
        If levels(k) = level Then
            a = cum
            b = cum + shares(k)
            Exit Sub
        End If
        cum = cum + shares(k)
    Next k
End Sub

Private Function DriftRatio(factor As String, level As String, sex As String, answerAge As Long, age As Long) As Double
    Dim w As Double, a As Double, b As Double, la As Double, lb As Double
    Dim levels() As String, shares() As Double, k As Long, cum As Double, total As Double, overlap As Double
    w = Taper(age)
    DriftRatio = Hazard(factor, level, sex) ^ w
    If factor <> "activity" And factor <> "bmi" Then Exit Function
    If GroupLo(age) = GroupLo(answerAge) Then Exit Function
    Slice sex, GroupLo(answerAge), factor, level, a, b
    If a < 0 Then Exit Function                 ' level not in the mix (underweight): held as answered
    If b <= a Then Exit Function
    ' the levels are listed in order of the answer in Mix, so the slices run in order
    Mix sex, GroupLo(age), factor, levels, shares
    cum = 0#
    total = 0#
    For k = LBound(levels) To UBound(levels)
        la = cum
        lb = cum + shares(k)
        overlap = MinOf(b, lb) - MaxOf(a, la)
        If overlap > 0 Then total = total + overlap * Hazard(factor, levels(k), sex) ^ w
        cum = lb
    Next k
    DriftRatio = total / (b - a)
End Function

Private Function MinOf(x As Double, y As Double) As Double
    If x < y Then MinOf = x Else MinOf = y
End Function

Private Function MaxOf(x As Double, y As Double) As Double
    If x > y Then MaxOf = x Else MaxOf = y
End Function

' ---------------------------------------------------------------- quitting smoking (A27)

Private Function SmokingRatio(p As Person, age As Long) As Double
    Dim level As String, w As Double, still As Double, quit As Double, total As Double, y As Long
    level = LevelOf(p, "smoking")
    w = Taper(age)
    If level <> "current" Or p.Keeps Or age <= p.Age Then
        SmokingRatio = Hazard("smoking", level, p.Sex) ^ w
        Exit Function
    End If
    still = 1#
    total = 0#
    For y = p.Age To age - 1                     ' quits during the year of age y
        If y >= QUIT_FROM_AGE Then
            quit = still * QUIT_RATE
            total = total + quit * Hazard("smoking", QuitLevel(y), p.Sex) ^ w
            still = still - quit
        End If
    Next y
    SmokingRatio = total + still * Hazard("smoking", "current", p.Sex) ^ w
End Function

' ---------------------------------------------------------------- combining (A08)

Private Function PersonMultiplier(p As Person, age As Long) As Double
    PersonMultiplier = SmokingRatio(p, age) _
        * DriftRatio("activity", LevelOf(p, "activity"), p.Sex, p.Age, age) _
        * DriftRatio("bmi", LevelOf(p, "bmi"), p.Sex, p.Age, age) _
        * DriftRatio("alcohol", LevelOf(p, "alcohol"), p.Sex, p.Age, age) _
        * DriftRatio("fruit_veg", LevelOf(p, "fruit_veg"), p.Sex, p.Age, age)
End Function

Private Function RelativeMultiplier(p As Person, age As Long) As Double
    Dim r As Double
    If age >= MAX_AGE Then
        RelativeMultiplier = 1#
        Exit Function
    End If
    r = PersonMultiplier(p, age) / AverageMultiplier(p.Sex, age)
    If r < CAP_LOW Then r = CAP_LOW
    If r > CAP_HIGH Then r = CAP_HIGH
    RelativeMultiplier = r
End Function

Private Function PersonalQ(p As Person, age As Long) As Double
    If age >= MAX_AGE Then
        PersonalQ = 1#
    Else
        PersonalQ = 1 - (1 - BaseQ(p.Region, p.Sex, age)) ^ RelativeMultiplier(p, age)
    End If
End Function

Private Function LifeExpectancy(p As Person) As Double
    ' UDD: sum of k p x, plus a half
    Dim age As Long, alive As Double, total As Double
    alive = 1#
    total = 0#
    For age = p.Age To MAX_AGE
        alive = alive * (1 - PersonalQ(p, age))
        total = total + alive
    Next age
    LifeExpectancy = total + 0.5
End Function

' ---------------------------------------------------------------- reference sheet

Private Function ReadPerson(caseName As String, found As Boolean) As Person
    Dim p As Person, i As Long, cc As Long, cq As Long
    found = False
    cc = ColumnOf(RefData, "case")
    cq = ColumnOf(RefData, "quit_age")
    For i = 2 To UBound(RefData, 1)
        If RefData(i, cc) = caseName Then
            p.Sex = RefData(i, ColumnOf(RefData, "sex"))
            p.Age = RefData(i, ColumnOf(RefData, "age"))
            p.Region = RefData(i, ColumnOf(RefData, "region"))
            p.Smoking = RefData(i, ColumnOf(RefData, "smoking"))
            If IsEmpty(RefData(i, cq)) Then p.QuitAge = 0 Else p.QuitAge = RefData(i, cq)
            p.Keeps = (UCase(CStr(RefData(i, ColumnOf(RefData, "keeps_smoking")))) = "TRUE")
            p.Minutes = RefData(i, ColumnOf(RefData, "activity_minutes"))
            p.HeightCm = RefData(i, ColumnOf(RefData, "height_cm"))
            p.WeightKg = RefData(i, ColumnOf(RefData, "weight_kg"))
            p.Drinks = RefData(i, ColumnOf(RefData, "drinks_per_week"))
            p.FruitVeg = RefData(i, ColumnOf(RefData, "fruit_veg_per_day"))
            found = True
            ReadPerson = p
            Exit Function
        End If
    Next i
End Function

Private Function PythonValue(caseName As String, measure As String, atAge As Long) As Double
    Dim i As Long, cc As Long, cm As Long, ca As Long, cv As Long
    cc = ColumnOf(RefData, "case"): cm = ColumnOf(RefData, "measure")
    ca = ColumnOf(RefData, "at_age"): cv = ColumnOf(RefData, "value")
    For i = 2 To UBound(RefData, 1)
        If RefData(i, cc) = caseName And RefData(i, cm) = measure And RefData(i, ca) = atAge Then
            PythonValue = RefData(i, cv)
            Exit Function
        End If
    Next i
    Err.Raise vbObjectError + 5, , "No Python value for " & caseName & " " & measure & " " & atAge
End Function

' ---------------------------------------------------------------- macros

Public Sub RunCase()
    Dim ws As Worksheet, caseName As String, p As Person, found As Boolean
    Dim age As Long, r As Long, alive As Double, q As Double, pyQ As Double, e As Double
    LoadData
    Set ws = ThisWorkbook.Worksheets("Results")
    caseName = CStr(ws.Range("B1").Value)
    p = ReadPerson(caseName, found)
    If Not found Then
        MsgBox "No case called '" & caseName & "' in the Reference sheet.", vbExclamation
        Exit Sub
    End If
    ws.Range("A3:K200").ClearContents
    ws.Range("A3:K3").Value = Array("age", "taper", "average multiplier", "person multiplier", _
        "relative multiplier r", "2017-2019 q", "personal q (VBA)", "personal q (Python)", _
        "difference", "alive at end of year", "")
    ws.Range("A3:K3").Font.Bold = True
    alive = 1#
    r = 4
    For age = p.Age To MAX_AGE
        q = PersonalQ(p, age)
        pyQ = PythonValue(caseName, "personal_q", age)
        alive = alive * (1 - q)
        ws.Cells(r, 1).Value = age
        ws.Cells(r, 2).Value = Taper(age)
        ws.Cells(r, 3).Value = AverageMultiplier(p.Sex, age)
        ws.Cells(r, 4).Value = PersonMultiplier(p, age)
        ws.Cells(r, 5).Value = RelativeMultiplier(p, age)
        ws.Cells(r, 6).Value = BaseQ(p.Region, p.Sex, age)
        ws.Cells(r, 7).Value = q
        ws.Cells(r, 8).Value = pyQ
        ws.Cells(r, 9).Value = q - pyQ
        ws.Cells(r, 10).Value = alive
        r = r + 1
    Next age
    e = LifeExpectancy(p)
    ws.Range("D1").Value = "Life expectancy, VBA:"
    ws.Range("E1").Value = e
    ws.Range("F1").Value = "Python:"
    ws.Range("G1").Value = PythonValue(caseName, "life_expectancy", p.Age)
    ws.Range("H1").Value = "difference:"
    ws.Range("I1").Value = e - ws.Range("G1").Value
    ws.Columns("A:J").AutoFit
End Sub

Public Sub CheckAllCases()
    Dim ws As Worksheet, i As Long, cc As Long, cm As Long, ca As Long, cv As Long, cs As Long
    Dim caseName As String, measure As String, atAge As Long, sex As String, current As String
    Dim vbaValue As Double, diff As Double, p As Person, found As Boolean
    Dim worstAvg As Double, worstR As Double, worstQ As Double, worstE As Double
    Dim nAvg As Long, nR As Long, nQ As Long, nE As Long, out As Long, allPass As Boolean
    LoadData
    cc = ColumnOf(RefData, "case"): cm = ColumnOf(RefData, "measure")
    ca = ColumnOf(RefData, "at_age"): cv = ColumnOf(RefData, "value"): cs = ColumnOf(RefData, "sex")
    Set ws = ThisWorkbook.Worksheets("Summary")
    ws.Cells.ClearContents
    ws.Range("A1:E1").Value = Array("case", "life expectancy (VBA)", "life expectancy (Python)", "difference", "")
    ws.Range("A1:E1").Font.Bold = True
    out = 2
    Application.ScreenUpdating = False
    For i = 2 To UBound(RefData, 1)
        caseName = CStr(RefData(i, cc))
        measure = CStr(RefData(i, cm))
        atAge = RefData(i, ca)
        Select Case measure
        Case "average_multiplier"
            sex = CStr(RefData(i, cs))
            diff = Abs(AverageMultiplier(sex, atAge) - RefData(i, cv))
            If diff > worstAvg Then worstAvg = diff
            nAvg = nAvg + 1
        Case "relative_multiplier", "personal_q", "life_expectancy"
            If caseName <> current Then           ' read each person once
                p = ReadPerson(caseName, found)
                current = caseName
            End If
            If measure = "relative_multiplier" Then
                diff = Abs(RelativeMultiplier(p, atAge) - RefData(i, cv))
                If diff > worstR Then worstR = diff
                nR = nR + 1
            ElseIf measure = "personal_q" Then
                diff = Abs(PersonalQ(p, atAge) - RefData(i, cv))
                If diff > worstQ Then worstQ = diff
                nQ = nQ + 1
            Else
                vbaValue = LifeExpectancy(p)
                diff = Abs(vbaValue - RefData(i, cv))
                If diff > worstE Then worstE = diff
                nE = nE + 1
                ws.Cells(out, 1).Value = caseName
                ws.Cells(out, 2).Value = vbaValue
                ws.Cells(out, 3).Value = RefData(i, cv)
                ws.Cells(out, 4).Value = vbaValue - RefData(i, cv)
                out = out + 1
            End If
        End Select
    Next i
    Application.ScreenUpdating = True
    out = out + 1
    ws.Cells(out, 1).Value = "measure"
    ws.Cells(out, 2).Value = "values"
    ws.Cells(out, 3).Value = "largest difference"
    ws.Cells(out, 4).Value = "within " & TOLERANCE
    ws.Range(ws.Cells(out, 1), ws.Cells(out, 4)).Font.Bold = True
    allPass = True
    WriteRow ws, out + 1, "average_multiplier", nAvg, worstAvg, allPass
    WriteRow ws, out + 2, "relative_multiplier", nR, worstR, allPass
    WriteRow ws, out + 3, "personal_q", nQ, worstQ, allPass
    WriteRow ws, out + 4, "life_expectancy", nE, worstE, allPass
    ws.Cells(out + 6, 1).Value = IIf(allPass, "PASS: every value agrees with the Python engine", _
                                     "FAIL: see the largest differences above")
    ws.Cells(out + 6, 1).Font.Bold = True
    ws.Columns("A:D").AutoFit
    MsgBox ws.Cells(out + 6, 1).Value & " (" & (nAvg + nR + nQ + nE) & " values).", vbInformation
End Sub

Private Sub WriteRow(ws As Worksheet, r As Long, name As String, n As Long, worst As Double, allPass As Boolean)
    ws.Cells(r, 1).Value = name
    ws.Cells(r, 2).Value = n
    ws.Cells(r, 3).Value = worst
    ws.Cells(r, 4).Value = (worst < TOLERANCE)
    If worst >= TOLERANCE Then allPass = False
End Sub
