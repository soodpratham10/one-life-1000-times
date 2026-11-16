# One Life, 1,000 Times: compare the independent R rebuild with the Python engine.
#
# Run from the project folder (Terminal):
#     Rscript crosscheck/r/run_crosscheck.R
# or in RStudio, with the working directory anywhere inside the project:
#     source("crosscheck/r/run_crosscheck.R")
#
# Part 1, risk engine: reads crosscheck/reference/risk_reference.csv (written by
#   python crosscheck/make_reference.py), recomputes every value in R, and writes
#   crosscheck/results/r_vs_python.csv with both answers and the difference.
# Part 2, cancer link: runs the synthetic cohort in R with the engine's solved
#   rates (cancer_reference.csv) and checks it reproduces the official deaths
#   at every age; writes crosscheck/results/r_cancer_cohort.csv.
# Part 3, CPP improvement (A28, the default): re-solves the 2019-2025 scales with
#   uniroot and compares scales, factors and improved death rates with cpp_reference.csv;
#   writes crosscheck/results/r_cpp_vs_python.csv.
# Part 4, CIA improvement (only with the CIA file on this computer):
#   compares improvement factors and improved death rates with cia_reference.csv;
#   writes crosscheck/results/cia_r_vs_python.csv (not committed).

local({
  d <- normalizePath(getwd())
  while (!file.exists(file.path(d, "pytest.ini"))) {
    if (dirname(d) == d) stop("Run this from inside the one-life-1000-times project folder")
    d <- dirname(d)
  }
  source(file.path(d, "crosscheck", "r", "risk.R"))
  source(file.path(d, "crosscheck", "r", "improvement.R"))
  source(file.path(d, "crosscheck", "r", "cancer_link.R"))
})
all_pass <- TRUE

TOLERANCE <- 1e-9

ref <- read.csv(file.path(ROOT, "crosscheck", "reference", "risk_reference.csv"), stringsAsFactors = FALSE)
ref$keeps_smoking <- as.logical(as.character(ref$keeps_smoking))
ref$r_value <- NA_real_

# population average multiplier
pop <- ref$measure == "average_multiplier"
ref$r_value[pop] <- mapply(average_multiplier, ref$sex[pop], ref$at_age[pop])

# each person
for (name in unique(ref$case[!pop])) {
  rows <- which(ref$case == name)
  first <- ref[rows[1], ]
  p <- list(sex = first$sex, age = first$age, region = first$region, smoking = first$smoking,
            quit_age = first$quit_age, keeps_smoking = isTRUE(first$keeps_smoking),
            activity_minutes = first$activity_minutes, height_cm = first$height_cm,
            weight_kg = first$weight_kg, drinks_per_week = first$drinks_per_week,
            fruit_veg_per_day = first$fruit_veg_per_day)
  q <- personal_q(p)
  for (i in rows) {
    a <- ref$at_age[i]
    ref$r_value[i] <- switch(ref$measure[i],
      relative_multiplier = relative_multiplier(p, a),
      personal_q = q[a - p$age + 1],
      life_expectancy = life_expectancy(q),
      stop("unknown measure ", ref$measure[i]))
  }
}

ref$difference <- ref$r_value - ref$value
out_dir <- file.path(ROOT, "crosscheck", "results")
dir.create(out_dir, showWarnings = FALSE)
write.csv(ref[, c("case", "measure", "at_age", "value", "r_value", "difference")],
          file.path(out_dir, "r_vs_python.csv"), row.names = FALSE)
names(ref)[names(ref) == "value"] <- "python_value"

cat(sprintf("R rebuild vs Python engine: %d values, %d people\n\n",
            nrow(ref), length(unique(ref$case[!pop]))))
summary_table <- aggregate(abs(difference) ~ measure, data = ref, FUN = max)
names(summary_table) <- c("measure", "largest_difference")
summary_table$values <- as.vector(table(ref$measure)[summary_table$measure])
summary_table$within_tolerance <- summary_table$largest_difference < TOLERANCE
print(summary_table, row.names = FALSE)

cat("\nLife expectancy (no improvement):\n")
e <- ref[ref$measure == "life_expectancy", ]
print(data.frame(case = e$case, python = round(e$python_value, 6), r = round(e$r_value, 6)),
      row.names = FALSE)

if (all(summary_table$within_tolerance)) {
  cat(sprintf("\nPASS: every value agrees to within %g.\n", TOLERANCE))
} else {
  all_pass <- FALSE
  worst <- ref[order(-abs(ref$difference)), ][1:10, c("case", "measure", "at_age", "python_value", "r_value", "difference")]
  cat("\nFAIL: the largest differences are:\n")
  print(worst, row.names = FALSE)
}
cat(sprintf("Wrote %s\n", file.path("crosscheck", "results", "r_vs_python.csv")))

# ================================================================ part 2: cancer link (A22)

cat("\n---- Part 2: cancer link calibration (A22) ----\n")
cancer_ref <- read.csv(file.path(ROOT, "crosscheck", "reference", "cancer_reference.csv"), stringsAsFactors = FALSE)
cohort <- do.call(rbind, lapply(c("M", "F"), function(sex) check_cancer_cohort(sex, cancer_ref[cancer_ref$sex == sex, ])))
write.csv(cohort, file.path(out_dir, "r_cancer_cohort.csv"), row.names = FALSE)
rel <- function(model, official) abs(model - official) / pmax(abs(official), 1e-300)
worst <- c(
  other_causes = max(rel(cohort$model_other_causes, cohort$official_other_causes)),
  lung_cancer = max(rel(cohort$model_lung[cohort$official_lung > 0], cohort$official_lung[cohort$official_lung > 0])),
  other_cancer = max(rel(cohort$model_other_cancer, cohort$official_other_cancer)))
cat("Largest relative difference between the R cohort's deaths and the official deaths, ages 18-109:\n")
print(signif(worst, 3))
zero_lung_ok <- all(cohort$model_lung[cohort$official_lung == 0] == 0)
bounds_ok <- all(cohort$s_lung <= S_MAX + 1e-12 & cohort$s_other <= S_MAX + 1e-12 &
                   cohort$s_lung >= 0 & cohort$s_other >= 0 & cohort$r_lung >= 0 & cohort$r_other >= 0)
surv <- cancer_ref[grepl("five_year_survival", cancer_ref$measure), ]
surv$r_value <- mapply(function(sex, m, a) {
  s <- cancer_ref$value[cancer_ref$sex == sex & cancer_ref$measure == ifelse(grepl("lung", m), "s_lung", "s_other")]
  five_year_survival(s, a)
}, surv$sex, surv$measure, surv$at_age)
surv_ok <- max(abs(surv$r_value - surv$value)) < 1e-12
show <- surv[surv$at_age %in% c(50, 60, 70) & surv$measure == "five_year_survival_lung", c("sex", "at_age", "value", "r_value")]
cat("\nLung cancer 5-year survival implied by the solved rates (Python vs R):\n")
print(show, row.names = FALSE)
cancer_pass <- all(worst < 1e-9) && zero_lung_ok && bounds_ok && surv_ok
cat(if (cancer_pass) "\nPASS: the cohort reproduces official total, lung and other-cancer deaths at every age;\n      excess rates within 0 to 3; survival formula agrees.\n"
    else "\nFAIL: see crosscheck/results/r_cancer_cohort.csv\n")
all_pass <- all_pass && cancer_pass

# ================================================================ part 3: CPP improvement (A28)

cat("\n---- Part 3: CPP report improvement (A28, the default) ----\n")
cpp <- read.csv(file.path(ROOT, "crosscheck", "reference", "cpp_reference.csv"), stringsAsFactors = FALSE)
cpp$r_value <- NA_real_
for (i in seq_len(nrow(cpp))) {
  m <- cpp$measure[i]
  if (m == "scale_under_65") cpp$r_value[i] <- cpp_scale(cpp$sex[i])[1]
  if (m == "scale_65_plus") cpp$r_value[i] <- cpp_scale(cpp$sex[i])[2]
  if (m == "improvement_factor") cpp$r_value[i] <- cpp_factor(cpp$sex[i], cpp$at_age[i], cpp$year[i])
}
for (name in unique(cpp$case[grepl("improved", cpp$measure)])) {
  f <- ref[ref$case == name, ][1, ]
  p <- list(sex = f$sex, age = f$age, region = f$region, smoking = f$smoking, quit_age = f$quit_age,
            keeps_smoking = isTRUE(f$keeps_smoking), activity_minutes = f$activity_minutes,
            height_cm = f$height_cm, weight_kg = f$weight_kg, drinks_per_week = f$drinks_per_week,
            fruit_veg_per_day = f$fruit_veg_per_day)
  rows <- which(cpp$case == name)
  q <- personal_q_cpp(p, cpp$year[rows[1]])
  for (i in rows) {
    cpp$r_value[i] <- if (cpp$measure[i] == "life_expectancy_improved") life_expectancy(q) else
      q[cpp$at_age[i] - p$age + 1]
  }
}
cpp$difference <- cpp$r_value - cpp$value
write.csv(cpp, file.path(out_dir, "r_cpp_vs_python.csv"), row.names = FALSE)
cpp_summary <- aggregate(abs(difference) ~ measure, data = cpp, FUN = max)
names(cpp_summary) <- c("measure", "largest_difference")
print(cpp_summary, row.names = FALSE)
cat("\nScales on the 2019-2025 rates (Python vs R):\n")
print(cpp[grepl("scale", cpp$measure), c("sex", "measure", "value", "r_value")], row.names = FALSE)
cpp_pass <- all(cpp_summary$largest_difference < TOLERANCE)
cat(if (cpp_pass) sprintf("\nPASS: every CPP improvement value agrees to within %g.\n", TOLERANCE) else
  "\nFAIL: see crosscheck/results/r_cpp_vs_python.csv\n")
all_pass <- all_pass && cpp_pass

# ================================================================ part 4: CIA improvement (A05)

cat("\n---- Part 4: CIA MI-2024 improvement ----\n")
cia_ref_path <- file.path(ROOT, "crosscheck", "reference", "cia_reference.csv")
if (!has_cia() || !file.exists(cia_ref_path)) {
  cat("Skipped: the CIA file or cia_reference.csv is not on this computer\n",
      "(build them with python pipeline/03_clean_mi2024.py, then python crosscheck/make_reference.py).\n")
} else {
  cia <- read.csv(cia_ref_path, stringsAsFactors = FALSE)
  cia$r_value <- NA_real_
  imp <- cia$measure == "improvement_factor"
  cia$r_value[imp] <- mapply(improvement_factor, cia$sex[imp], cia$at_age[imp], cia$year[imp])
  for (name in unique(cia$case[!imp])) {
    f <- ref[ref$case == name, ][1, ]
    p <- list(sex = f$sex, age = f$age, region = f$region, smoking = f$smoking, quit_age = f$quit_age,
              keeps_smoking = isTRUE(f$keeps_smoking), activity_minutes = f$activity_minutes,
              height_cm = f$height_cm, weight_kg = f$weight_kg, drinks_per_week = f$drinks_per_week,
              fruit_veg_per_day = f$fruit_veg_per_day)
    rows <- which(cia$case == name)
    q <- personal_q_improved(p, cia$year[rows[1]])
    for (i in rows) {
      cia$r_value[i] <- if (cia$measure[i] == "life_expectancy_improved") life_expectancy(q) else
        q[cia$at_age[i] - p$age + 1]
    }
  }
  cia$difference <- cia$r_value - cia$value
  write.csv(cia, file.path(out_dir, "cia_r_vs_python.csv"), row.names = FALSE)
  cia_summary <- aggregate(abs(difference) ~ measure, data = cia, FUN = max)
  names(cia_summary) <- c("measure", "largest_difference")
  print(cia_summary, row.names = FALSE)
  e <- cia[cia$measure == "life_expectancy_improved", ]
  cat("\nLife expectancy with improvement, from 2026 (Python vs R):\n")
  print(data.frame(case = e$case, python = round(e$value, 4), r = round(e$r_value, 4)), row.names = FALSE)
  cia_pass <- all(cia_summary$largest_difference < TOLERANCE)
  cat(if (cia_pass) sprintf("\nPASS: every improvement value agrees to within %g.\n", TOLERANCE) else "\nFAIL: see crosscheck/results/cia_r_vs_python.csv\n")
  all_pass <- all_pass && cia_pass
}

cat(if (all_pass) "\nALL PARTS PASS\n" else "\nSOMETHING FAILED (see above)\n")
