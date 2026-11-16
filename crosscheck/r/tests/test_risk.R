# Tests for the R rebuild (crosscheck/r/risk.R).
#
# Run from the project folder:
#     Rscript -e 'testthat::test_file("crosscheck/r/tests/test_risk.R")'
# Needs the testthat package: install.packages("testthat")

library(testthat)

local({
  d <- normalizePath(getwd())
  while (!file.exists(file.path(d, "pytest.ini"))) {
    if (dirname(d) == d) stop("Run this from inside the one-life-1000-times project folder")
    d <- dirname(d)
  }
  source(file.path(d, "crosscheck", "r", "risk.R"))
})

test_that("taper is 1 to 79, then falls in a straight line to 0 at 110", {
  expect_equal(taper(60), 1)
  expect_equal(taper(79), 1)
  expect_equal(taper(95), 15 / 31)
  expect_equal(taper(110), 0)
})

test_that("hazard ratios use the sex-specific value, else the both-sexes one", {
  expect_equal(hazard("smoking", "current", "M"), 2.8)
  expect_equal(hazard("smoking", "current", "F"), 3.0)
  expect_equal(hazard("activity", "none", "F"), 1.0)
  expect_equal(hazard("bmi", "40_plus", "M"), 2.76)
  expect_error(hazard("smoking", "sometimes", "M"))
})

test_that("every population mix adds to 1", {
  for (sex in c("M", "F")) for (g in AGE_GROUPS) {
    mix <- pop_mix(sex, g)
    for (f in names(mix)) expect_equal(sum(mix[[f]]), 1, tolerance = 1e-12)
  }
})

test_that("base rates: 111 ages ending in q = 1, and PEI has its own table", {
  q <- base_q("MB", "M")
  expect_length(q, 111)
  expect_equal(q[111], 1)
  expect_false(identical(base_q("PE", "F"), base_q("NS", "F")))
})

test_that("drift by hand: normal BMI at 25, read at 40 (A26)", {
  young <- pop_mix("M", c(18, 34))$bmi[["18.5_25"]]
  m35 <- pop_mix("M", c(35, 49))$bmi
  normal <- m35[["18.5_25"]]
  expect_true(normal < young && young < normal + m35[["25_27.5"]])
  expected <- (normal * 1 + (young - normal) * 1.07) / young
  expect_equal(drift_ratio("bmi", "18.5_25", "M", 25, 40), expected, tolerance = 1e-12)
  expect_equal(drift_ratio("bmi", "18.5_25", "M", 25, 30), 1)       # same age group: no drift
  expect_equal(drift_ratio("bmi", "under_18.5", "M", 25, 60), 1.51)  # underweight is held
})

test_that("drift keeps the population average exactly (A26)", {
  for (sex in c("M", "F")) for (f in names(DRIFT_ORDER)) {
    start <- pop_mix(sex, c(18, 34))[[f]]
    later <- pop_mix(sex, c(50, 64))[[f]]
    drifted <- sum(vapply(names(start), function(l) start[[l]] * drift_ratio(f, l, sex, 25, 55), 0))
    direct <- sum(vapply(names(later), function(l) later[[l]] * hazard(f, l, sex), 0))
    expect_equal(drifted, direct, tolerance = 1e-12)
  }
})

test_that("smoking path by hand: answer at 33, read at 37 (A27)", {
  r <- QUIT_RATE
  path <- smoking_path("current", FALSE, 33, 37)
  expect_equal(path[["quit_before_35"]], r + (1 - r) * r)
  expect_equal(path[["quit_35_44"]], (1 - r)^2 * r + (1 - r)^3 * r)
  expect_equal(path[["current"]], (1 - r)^4)
  expect_equal(sum(path), 1)
  expect_equal(smoking_path("current", FALSE, 18, 25), c(current = 1))   # no quitting before 25
  expect_equal(smoking_path("current", TRUE, 30, 90), c(current = 1))    # keeps smoking
  expect_equal(smoking_path("never", FALSE, 30, 90), c(never = 1))
})

test_that("the relative multiplier is capped", {
  p <- list(sex = "M", age = 40, region = "CA", smoking = "current", quit_age = NA, keeps_smoking = TRUE,
            activity_minutes = 0, height_cm = 170, weight_kg = 130, drinks_per_week = 50,
            fruit_veg_per_day = 0)
  expect_equal(relative_multiplier(p, 40), CAP_HIGH)
  expect_equal(relative_multiplier(p, 110), 1)
})

test_that("R agrees with the Python engine on every reference value", {
  ref <- read.csv(file.path(ROOT, "crosscheck", "reference", "risk_reference.csv"), stringsAsFactors = FALSE)
  ref$keeps_smoking <- as.logical(as.character(ref$keeps_smoking))
  pop <- ref[ref$measure == "average_multiplier", ]
  expect_equal(unname(mapply(average_multiplier, pop$sex, pop$at_age)), pop$value, tolerance = 1e-12)
  for (name in unique(ref$case[ref$measure == "life_expectancy"])) {
    rows <- ref[ref$case == name, ]
    f <- rows[1, ]
    p <- list(sex = f$sex, age = f$age, region = f$region, smoking = f$smoking, quit_age = f$quit_age,
              keeps_smoking = isTRUE(f$keeps_smoking), activity_minutes = f$activity_minutes,
              height_cm = f$height_cm, weight_kg = f$weight_kg, drinks_per_week = f$drinks_per_week,
              fruit_veg_per_day = f$fruit_veg_per_day)
    q <- personal_q(p)
    expect_equal(q, rows$value[rows$measure == "personal_q"], tolerance = 1e-12, info = name)
    expect_equal(life_expectancy(q), rows$value[rows$measure == "life_expectancy"],
                 tolerance = 1e-10, info = name)
  }
})
