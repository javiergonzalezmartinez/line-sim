# line-sim

Discrete-event simulator of a serial production line with finite buffers, random failures and blocked/starved accounting. Python standard library only.

    python3 -m linesim examples/line.json --out report.html
    python3 -m unittest discover -s tests -t .

The example line is fictitious and illustrative. It does not describe any real plant.

## What you learn here
Why a line runs below its slowest station: blocking and starving, failures, and what a buffer is worth. Buffer size 0 (direct hand-off) is not modelled; minimum is 1.

## Whole-plant model (plantsim)
Batch flow of a fictitious oral-solid-dose plant, warehouse receipt to dispatch: receipt and quarantine, QC sampling and release (day shift), dispensing, granulation, compression, coating, packaging, QC lab release (retests), QA record review, dispatch waves. Changeover and cleaning when the product changes, breakdowns, working calendars.

    python3 -m plantsim examples/pharma.json --view plant.html

`plant.html` is an offline animated 2D view (batches move through the stages; use the slider or add `#t=330` to the URL).

Not modelled yet: finite buffers between stages, shift handovers, material shortages, deviations and QA holds beyond a retest chance, campaign sizing. All numbers are invented and illustrative.
