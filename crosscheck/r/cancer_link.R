# One Life, 1,000 Times: R check of the cancer link calibration (A22).
#
# The Python engine solves, age by age, the excess death rate after a cancer
# diagnosis (s_lung, s_other), a small rate for undiagnosed people where needed
# (r_lung, r_other) and a scale on all other causes (eta), so that a synthetic
# cohort reproduces the official 2017-2019 deaths exactly. This file does not
# re-solve them. It takes the solved values from crosscheck/reference/
# cancer_reference.csv, runs the synthetic cohort forward in R, built from the
# description in docs/assumptions.md (A13, A22) and the raw CSV files, and
# checks the defining property: at every age 18-109, the cohort's total, lung
# cancer and other-cancer deaths equal the official ones. Source after risk.R.

S_MAX <- 3.0
W <- c(1, 1, 1, 1, 1, 0.25)                  # weight by years since diagnosis: 0, 1, 2, 3, 4, 5+
CAUSE_ORDER <- c("lung_cancer", "other_cancer", "heart", "stroke", "copd", "diabetes", "dementia",
                 "motor_vehicle", "other_accidents", "other_injury", "other")

CANCER_RATES <- read_data("data/clean/cancer_rates.csv")
DEATHS <- read_data("data/clean/causes_of_death.csv")

cancer_chance <- function(sex, age) {
  row <- CANCER_RATES[CANCER_RATES$sex == sex & CANCER_RATES$age_lo <= age & CANCER_RATES$age_hi >= age, ]
  if (nrow(row) != 1) stop("expected one cancer rate row for ", sex, " ", age)
  c(lung = row$p_lung, other = row$p_other_cancer)
}

cancer_shares <- function(sex, age) {
  # share of 2017-2019 deaths that were lung and other cancer, among the 11 cause groups
  rows <- DEATHS[DEATHS$year %in% 2017:2019 & DEATHS$sex == sex &
                   DEATHS$age_lo <= age & DEATHS$age_hi >= age, ]
  by_cause <- tapply(rows$deaths, rows$cause, sum)
  if (!is.na(by_cause["covid"]) && by_cause[["covid"]] != 0) stop("COVID deaths in the base years")
  counts <- vapply(CAUSE_ORDER, function(c) if (is.na(by_cause[c])) 0 else by_cause[[c]], 0)
  c(lung = counts[["lung_cancer"]], other = counts[["other_cancer"]]) / sum(counts)
}

age_shift <- function(diag, new) c(new, diag[1:4], diag[5] + diag[6])

# deaths from each force when the forces compete within the year (constant forces)
compete <- function(mass, forces) {
  total <- sum(forces)
  if (total == 0) return(list(deaths = 0 * forces, q = 0))
  q <- 1 - exp(-total)
  list(deaths = mass * q * forces / total, q = q)
}

check_cancer_cohort <- function(sex, cal) {
  # cal: data frame with columns measure, at_age, value for this sex
  get <- function(m, a) cal$value[cal$measure == m & cal$at_age == a]
  q <- base_q("CA", sex)
  pu <- 1
  pl <- rep(0, 6)
  po <- rep(0, 6)
  out <- data.frame()
  for (age in MIN_AGE:(MAX_AGE - 1)) {
    ch <- cancer_chance(sex, age)
    pl <- age_shift(pl, pu * ch[["lung"]])
    po <- age_shift(po, pu * (1 - ch[["lung"]]) * ch[["other"]])
    pu <- pu * (1 - ch[["lung"]]) * (1 - ch[["other"]])
    mass <- pu + sum(pl) + sum(po)
    sh <- cancer_shares(sex, age)
    mu <- -log(1 - q[age + 1])
    official <- mass * q[age + 1] * c(1 - sh[["lung"]] - sh[["other"]], sh[["lung"]], sh[["other"]])

    h_nc <- get("eta", age) * mu * (1 - sh[["lung"]] - sh[["other"]])
    s_l <- get("s_lung", age); s_o <- get("s_other", age)
    r_l <- get("r_lung", age); r_o <- get("r_other", age)

    und <- compete(pu, c(h_nc, r_l, r_o))
    deaths <- und$deaths
    q_l <- q_o <- numeric(6)
    for (d in 1:6) {
      l <- compete(pl[d], c(h_nc, s_l * W[d], 0))
      o <- compete(po[d], c(h_nc, 0, s_o * W[d]))
      deaths <- deaths + l$deaths + o$deaths
      q_l[d] <- l$q
      q_o[d] <- o$q
    }
    out <- rbind(out, data.frame(sex = sex, age = age,
                                 model_other_causes = deaths[1], official_other_causes = official[1],
                                 model_lung = deaths[2], official_lung = official[2],
                                 model_other_cancer = deaths[3], official_other_cancer = official[3],
                                 s_lung = s_l, s_other = s_o, r_lung = r_l, r_other = r_o))
    pu <- pu * (1 - und$q)
    pl <- pl * (1 - q_l)
    po <- po * (1 - q_o)
  }
  out
}

five_year_survival <- function(s, age) exp(-sum(s[age:(age + 4) - MIN_AGE + 1]))   # s indexed from age 18
