# One Life, 1,000 Times: R rebuild of future mortality improvement (A05, A09).
#
# q(age, year) = q(age, 2018) x product over s = 2019 .. year of (1 - MI(age, s))
# from the CIA MI-2024 scale. Ages under 20 use the age-20 rate; q = 1 at 110 is
# never improved; years after 2119 keep the 2119 rate; years up to 2018 get no
# improvement. Source this after risk.R. Needs data/clean/cia_mi2024.csv, which
# is built on your own computer (see README) and never committed.

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
