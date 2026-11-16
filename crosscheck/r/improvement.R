# One Life, 1,000 Times: R rebuild of future mortality improvement (A05, A09, A28).
#
# q(age, year) = q(age, 2018) x product over s = 2019 .. year of (1 - MI(age, s)).
# First the CIA MI-2024 scale (optional), then the CPP report basis (the default)
# at the end of this file. For the CIA scale: Ages under 20 use the age-20 rate; q = 1 at 110 is
# never improved; years after 2119 keep the 2119 rate; years up to 2018 get no
# improvement. Source this after risk.R. The CIA part needs data/clean/cia_mi2024.csv,
# which is built on your own computer (see README) and never committed.

MI_PATH <- file.path(ROOT, "data", "clean", "cia_mi2024.csv")
BASE_YEAR <- BASE_PERIOD + 1           # middle year of the 2017-2019 table
MI_LAST_YEAR <- 2119
MI_MIN_AGE <- 20

has_cia <- function() file.exists(MI_PATH)

MI_GRIDS <- new.env()

mi_grid <- function(sex) {
  # matrix [age 0..110, year 2019..2119] of improvement rates
  if (!is.null(MI_GRIDS[[sex]])) return(MI_GRIDS[[sex]])
  mi <- read.csv(MI_PATH, stringsAsFactors = FALSE)
  mi <- mi[mi$sex == sex & mi$year > BASE_YEAR & mi$year <= MI_LAST_YEAR & mi$age <= MAX_AGE, ]
  years <- (BASE_YEAR + 1):MI_LAST_YEAR
  grid <- matrix(0, nrow = MAX_AGE + 1, ncol = length(years))
  for (a in MI_MIN_AGE:MAX_AGE) {
    rows <- mi[mi$age == a, ]
    grid[a + 1, ] <- rows$mi[match(years, rows$year)]
  }
  if (anyNA(grid)) stop("MI-2024 file has gaps for ", sex)
  for (a in 0:(MI_MIN_AGE - 1)) grid[a + 1, ] <- grid[MI_MIN_AGE + 1, ]
  grid[MAX_AGE + 1, ] <- 0
  MI_GRIDS[[sex]] <- grid
  grid
}

improvement_factor <- function(sex, age, year) {
  if (year <= BASE_YEAR) return(1)
  grid <- mi_grid(sex)
  k <- year - BASE_YEAR                       # years of improvement
  n <- ncol(grid)
  rates <- grid[age + 1, seq_len(min(k, n))]
  extra <- max(0, k - n)
  prod(1 - rates) * (1 - grid[age + 1, n])^extra
}

personal_q_improved <- function(p, start_year) {
  ages <- p$age:MAX_AGE
  years <- start_year + (ages - p$age)
  q <- base_q(p$region, p$sex)[ages + 1]
  q <- q * mapply(function(a, y) improvement_factor(p$sex, a, y), ages, years)
  q <- pmin(pmax(q, 0), 1)
  r <- vapply(ages, function(a) relative_multiplier(p, a), 0)
  out <- 1 - (1 - q)^r
  out[length(out)] <- 1
  out
}

# ---------------------------------------------------------------- CPP report basis (A28), the default
#
# Rates from the 32nd CPP actuarial report, Table 41, by age band: the 2025 rate,
# the 2026-2038 average and the 2039+ ultimate rate. The 2019-2025 rates are the
# 2025 rate times a scale (one below 65, one from 65), solved here with uniroot so
# the period life expectancy in 2025 at 65, then at 0, equals the report's Table 43.

CPP <- read_data("data/assumptions/cpp32_improvement.csv")
CPP_LE <- read_data("data/assumptions/cpp32_life_expectancy.csv")
CPP_SPLIT_AGE <- 65

cpp_rate_row <- function(sex, age) {
  if (age >= MAX_AGE) return(c(0, 0, 0))
  r <- CPP[CPP$sex == sex & CPP$age_lo <= age & CPP$age_hi >= age, ]
  if (nrow(r) != 1) stop("no CPP rate for ", sex, " ", age)
  c(r$mi_2025, r$mi_2026_2038, r$mi_2039_plus) / 100
}

cpp_factor_scaled <- function(sex, age, year, scale) {
  if (year <= BASE_YEAR || age >= MAX_AGE) return(1)
  years <- (BASE_YEAR + 1):year
  n1 <- sum(years <= 2025)
  n2 <- sum(years >= 2026 & years <= 2038)
  n3 <- sum(years >= 2039)
  m <- cpp_rate_row(sex, age)
  k <- if (age < CPP_SPLIT_AGE) scale[1] else scale[2]
  (1 - k * m[1])^n1 * (1 - m[2])^n2 * (1 - m[3])^n3
}

cpp_period_e <- function(sex, year, age, scale) {
  q <- base_q("CA", sex)
  for (a in 0:(MAX_AGE - 1)) q[a + 1] <- q[a + 1] * cpp_factor_scaled(sex, a, year, scale)
  life_expectancy(q[(age + 1):(MAX_AGE + 1)])
}

CPP_SCALES <- new.env()

cpp_scale <- function(sex) {
  if (!is.null(CPP_SCALES[[sex]])) return(CPP_SCALES[[sex]])
  target <- function(age) CPP_LE$e[CPP_LE$sex == sex & CPP_LE$basis == "period" &
                                       CPP_LE$year == 2025 & CPP_LE$age == age]
  old <- uniroot(function(k) cpp_period_e(sex, 2025, CPP_SPLIT_AGE, c(1, k)) - target(CPP_SPLIT_AGE),
                 c(-3, 3), tol = 1e-14)$root
  young <- uniroot(function(k) cpp_period_e(sex, 2025, 0, c(k, old)) - target(0), c(-3, 3), tol = 1e-14)$root
  CPP_SCALES[[sex]] <- c(young, old)
  CPP_SCALES[[sex]]
}

cpp_factor <- function(sex, age, year) cpp_factor_scaled(sex, age, year, cpp_scale(sex))

personal_q_cpp <- function(p, start_year) {
  ages <- p$age:MAX_AGE
  years <- start_year + (ages - p$age)
  q <- base_q(p$region, p$sex)[ages + 1] * mapply(function(a, y) cpp_factor(p$sex, a, y), ages, years)
  q <- pmin(pmax(q, 0), 1)
  r <- vapply(ages, function(a) relative_multiplier(p, a), 0)
  out <- 1 - (1 - q)^r
  out[length(out)] <- 1
  out
}
