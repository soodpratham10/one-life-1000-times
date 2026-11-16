# One Life, 1,000 Times: compare the independent R rebuild with the Python engine.
#
# Run from the project folder (Terminal):
#     Rscript crosscheck/r/run_crosscheck.R
# or in RStudio, with the working directory anywhere inside the project:
#     source("crosscheck/r/run_crosscheck.R")
#
# Reads crosscheck/reference/risk_reference.csv (written by
# python crosscheck/make_reference.py), recomputes every value in R, and writes
# crosscheck/results/r_vs_python.csv with both answers and the difference.

local({
  d <- normalizePath(getwd())
  while (!file.exists(file.path(d, "pytest.ini"))) {
    if (dirname(d) == d) stop("Run this from inside the one-life-1000-times project folder")
    d <- dirname(d)
  }
  source(file.path(d, "crosscheck", "r", "risk.R"))
})

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
  worst <- ref[order(-abs(ref$difference)), ][1:10, c("case", "measure", "at_age", "python_value", "r_value", "difference")]
  cat("\nFAIL: the largest differences are:\n")
  print(worst, row.names = FALSE)
}
cat(sprintf("Wrote %s\n", file.path("crosscheck", "results", "r_vs_python.csv")))
