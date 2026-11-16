# One Life, 1,000 Times: independent R rebuild of the risk engine (Phase 4).
#
# Rebuilt from the assumptions register (docs/assumptions.md: A04, A07, A08,
# A18, A19, A26, A27) and the raw CSV files, not translated line by line from
# the Python engine. Base R only. Covers:
#   - the 2017-2019 base death rates (StatCan life tables, PEI single-age table)
#   - the population mix of habits by sex and age group (CCHS, CTNS, splits)
#   - hazard ratios, taper and the population average multiplier
#   - habits that change with age (activity and BMI keep their rank, A26)
#   - quitting smoking (expected path, 5% a year from 25, A27)
#   - the capped relative multiplier, personal death rates, life expectancy
# No future improvement (the CIA file is not needed).
#
# Used by crosscheck/r/run_crosscheck.R and crosscheck/r/tests/test_risk.R.

# ---------------------------------------------------------------- constants

BASE_PERIOD <- 2017
MIN_AGE <- 18
MAX_AGE <- 110
CAP_LOW <- 0.35
CAP_HIGH <- 5.0
TAPER_START <- 79
GRAMS_PER_DRINK <- 13.45
QUIT_RATE <- 0.05
QUIT_FROM_AGE <- 25

FACTORS <- c("smoking", "activity", "bmi", "alcohol", "fruit_veg")
AGE_GROUPS <- list(c(18, 34), c(35, 49), c(50, 64), c(65, 110))

ACTIVITY_UNDER_150 <- c(none = 0.5, under_150 = 0.5)
ACTIVITY_150_PLUS <- c("150_299" = 0.5, "300_449" = 0.25, "450_plus" = 0.25)
OVERWEIGHT_SPLIT <- c("25_27.5" = 0.5, "27.5_30" = 0.5)
OBESE_SPLIT <- c("30_35" = 15.2 / 23.0, "35_40" = 5.1 / 23.0, "40_plus" = 2.7 / 23.0)
FORMER_SPLIT_UNDER_50 <- c(quit_before_35 = 0.75, quit_35_44 = 0.25)
FORMER_SPLIT_50_PLUS <- c(quit_before_35 = 0.4, quit_35_44 = 0.3, quit_45_54 = 0.2, quit_55_plus = 0.1)

# Levels in order of the answer, for habits that drift with age (A26)
DRIFT_ORDER <- list(
  activity = c("none", "under_150", "150_299", "300_449", "450_plus"),
  bmi = c("18.5_25", "25_27.5", "27.5_30", "30_35", "35_40", "40_plus")
)

# ---------------------------------------------------------------- data

find_root <- function() {
  d <- normalizePath(getwd())
  while (!file.exists(file.path(d, "pytest.ini"))) {
    parent <- dirname(d)
    if (parent == d) stop("Run this from inside the one-life-1000-times project folder")
    d <- parent
  }
  d
}

ROOT <- find_root()
read_data <- function(path) read.csv(file.path(ROOT, path), stringsAsFactors = FALSE)

LIFE <- read_data("data/clean/life_tables.csv")
LIFE_PEI <- read_data("data/clean/life_tables_pei.csv")
PREV <- read_data("data/clean/risk_prevalence.csv")
PREV$base <- as.logical(as.character(PREV$base))
FORMER <- read_data("data/assumptions/former_smokers.csv")
HR <- read_data("data/assumptions/hazard_ratios.csv")

# ---------------------------------------------------------------- base rates

base_q <- function(region, sex) {
  t <- if (region == "PE") LIFE_PEI else LIFE
  rows <- t[t$period_start == BASE_PERIOD & t$region == region & t$sex == sex, ]
  rows <- rows[order(rows$age), ]
  if (nrow(rows) != MAX_AGE + 1 || rows$qx[MAX_AGE + 1] != 1) {
    stop(sprintf("no complete 2017-2019 life table for %s %s", region, sex))
  }
  rows$qx                                   # element i is age i - 1
}

life_expectancy <- function(q) sum(cumprod(1 - q)) + 0.5    # UDD: sum of k p x, plus a half

# ---------------------------------------------------------------- hazard ratios and taper

hazard <- function(factor, level, sex) {
  for (s in c(sex, "B")) {
    v <- HR$hr[HR$factor == factor & HR$level == level & HR$sex == s]
    if (length(v) == 1) return(v)
  }
  stop(sprintf("no hazard ratio for %s %s %s", factor, level, sex))
}

taper <- function(age) {
  if (age <= TAPER_START) return(1)
  max(0, (MAX_AGE - age) / (MAX_AGE - TAPER_START))
}

age_group <- function(age) {
  for (g in AGE_GROUPS) if (age >= g[1] && age <= g[2]) return(g)
  stop(sprintf("no age group for %s", age))
}

# ---------------------------------------------------------------- population mix (A18, A19)

MIX_CACHE <- new.env()

pop_mix <- function(sex, group) {
  key <- paste(sex, group[1], group[2])
  if (!is.null(MIX_CACHE[[key]])) return(MIX_CACHE[[key]])
  rows <- PREV[which(PREV$base & PREV$region == "CA" & PREV$sex == sex &
                 PREV$age_lo == group[1] & PREV$age_hi == group[2]), ]
  pct <- setNames(rows$pct / 100, rows$indicator)
  former <- FORMER$pct[FORMER$sex == sex & FORMER$age_lo == group[1]] / 100
  if (length(former) != 1) stop("former smoker share missing")
  current <- pct[["current_smoker"]]
  split <- if (group[2] < 50) FORMER_SPLIT_UNDER_50 else FORMER_SPLIT_50_PLUS
  smoking <- c(never = 1 - current - former, current = current, former * split)

  active <- pct[["active_150"]]
  activity <- c((1 - active) * ACTIVITY_UNDER_150, active * ACTIVITY_150_PLUS)

  over <- pct[["overweight"]]
  obese <- pct[["obese"]]
  bmi <- c("18.5_25" = 1 - over - obese, over * OVERWEIGHT_SPLIT, obese * OBESE_SPLIT)

  five <- pct[["fruit_veg_5"]]
  fruit_veg <- c("0_2" = 1 - five, "5_plus" = five)

  mix <- list(smoking = smoking, activity = activity, bmi = bmi, alcohol = c(under_25g = 1),
              fruit_veg = fruit_veg)
  for (f in names(mix)) {
    if (min(mix[[f]]) < 0 || abs(sum(mix[[f]]) - 1) > 1e-9) stop(sprintf("%s mix does not add to 1", f))
  }
  MIX_CACHE[[key]] <- mix
  mix
}

average_multiplier <- function(sex, age) {
  w <- taper(age)
  mix <- pop_mix(sex, age_group(age))
  total <- 1
  for (f in FACTORS) {
    shares <- mix[[f]]
    total <- total * sum(vapply(names(shares), function(l) shares[[l]] * hazard(f, l, sex)^w, 0))
  }
  total
}

# ---------------------------------------------------------------- a person's levels

quit_level <- function(quit_age) {
  if (quit_age < 35) "quit_before_35" else if (quit_age < 45) "quit_35_44" else
    if (quit_age < 55) "quit_45_54" else "quit_55_plus"
}

person_levels <- function(p) {
  smoking <- if (p$smoking == "former") quit_level(p$quit_age) else p$smoking
  m <- p$activity_minutes
  activity <- if (m == 0) "none" else if (m < 150) "under_150" else
    if (m < 300) "150_299" else if (m < 450) "300_449" else "450_plus"
  b <- p$weight_kg / (p$height_cm / 100)^2
  bmi <- if (b < 18.5) "under_18.5" else if (b < 25) "18.5_25" else if (b < 27.5) "25_27.5" else
    if (b < 30) "27.5_30" else if (b < 35) "30_35" else if (b < 40) "35_40" else "40_plus"
  g <- p$drinks_per_week * GRAMS_PER_DRINK / 7
  alcohol <- if (g < 25) "under_25g" else if (g < 45) "25_44g" else
    if (g < 65) "45_64g" else "65g_plus"
  f <- p$fruit_veg_per_day
  fruit_veg <- if (f < 3) "0_2" else if (f < 4) "3" else if (f < 5) "4" else "5_plus"
  list(smoking = smoking, activity = activity, bmi = bmi, alcohol = alcohol, fruit_veg = fruit_veg)
}

# ---------------------------------------------------------------- habits that change with age (A26)

slices <- function(order, shares) {
  lo <- 0
  out <- list()
  for (l in order) {
    s <- if (l %in% names(shares)) shares[[l]] else 0
    out[[l]] <- c(lo, lo + s)
    lo <- lo + s
  }
  out
}

drift_ratio <- function(factor, level, sex, answer_age, age) {
  w <- taper(age)
  order <- DRIFT_ORDER[[factor]]
  if (is.null(order) || !(level %in% order) || identical(age_group(age), age_group(answer_age))) {
    return(hazard(factor, level, sex)^w)
  }
  mine <- slices(order, pop_mix(sex, age_group(answer_age))[[factor]])[[level]]
  if (mine[2] <= mine[1]) return(hazard(factor, level, sex)^w)
  later <- slices(order, pop_mix(sex, age_group(age))[[factor]])
  total <- 0
  for (l in names(later)) {
    overlap <- max(0, min(mine[2], later[[l]][2]) - max(mine[1], later[[l]][1]))
    total <- total + overlap * hazard(factor, l, sex)^w
  }
  total / (mine[2] - mine[1])
}

# ---------------------------------------------------------------- quitting smoking (A27)

smoking_path <- function(level, keeps, answer_age, age) {
  if (level != "current" || keeps || age <= answer_age) return(setNames(1, level))
  shares <- numeric(0)
  still <- 1
  for (y in answer_age:(age - 1)) {          # quits during the year of age y
    quit <- still * (if (y >= QUIT_FROM_AGE) QUIT_RATE else 0)
    if (quit > 0) {
      l <- quit_level(y)
      shares[l] <- (if (l %in% names(shares)) shares[[l]] else 0) + quit
      still <- still - quit
    }
  }
  c(shares, current = still)
}

# ---------------------------------------------------------------- combining (A08)

person_multiplier <- function(p, age) {
  lv <- person_levels(p)
  w <- taper(age)
  total <- 1
  for (f in FACTORS) {
    if (f == "smoking") {
      path <- smoking_path(lv$smoking, p$keeps_smoking, p$age, age)
      ratio <- sum(vapply(names(path), function(l) path[[l]] * hazard("smoking", l, p$sex)^w, 0))
    } else {
      ratio <- drift_ratio(f, lv[[f]], p$sex, p$age, age)
    }
    total <- total * ratio
  }
  total
}

relative_multiplier <- function(p, age) {
  if (age >= MAX_AGE) return(1)
  r <- person_multiplier(p, age) / average_multiplier(p$sex, age)
  min(max(r, CAP_LOW), CAP_HIGH)
}

personal_q <- function(p) {
  ages <- p$age:MAX_AGE
  q <- base_q(p$region, p$sex)[ages + 1]
  r <- vapply(ages, function(a) relative_multiplier(p, a), 0)
  out <- 1 - (1 - q)^r
  out[length(out)] <- 1                      # everyone dies in the open age group
  out
}
