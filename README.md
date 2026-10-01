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

`plant.html` is an offline interactive 2D view: floor-plan layout, lots as moving entities, forklifts as a shared resource pool, live charts (lots in the plant, cumulative finished, utilisation) and a parameter panel (release rate, servers per stage, forklifts, transport time, breakdowns, changeovers, 24/7 labs). Changing a parameter re-runs the simulation in the browser with `plantsim/engine.js`, a port of the Python model.
Use `examples/pharma_flow.json` for the material flow (dock, warehouse quarantine, dispensing, intermediate store, production, finished-goods hold, shipping) with forklift transport. Deep links: `#t=381&s=0.5&fk=1&mv=6` = start time, speed, forklifts, transport multiplier.

Tests: `python3 -m unittest discover -s tests -t .` and `node --test tests/`. The JS engine is checked against Python: identical completion times with randomness off, means within 3% over 20 seeds with randomness on.

Not modelled yet: finite buffers between stages, shift handovers, material shortages, deviations and QA holds beyond a retest chance, campaign sizing. All numbers are invented and illustrative.

## Signal and transaction layer
Every simulated lot generates PLC/sensor events (dock door, barcode scans, scales, conveyors, palletizer states, labelling, serialization, forklift RFID), WMS events (goods receipt, putaway and transfer orders, bin status), QA/LIMS events and ERP events (goods receipt, quarantine to unrestricted release, goods issue to production order, operation confirmations, backflush, outbound delivery and goods issue). The page shows a live log with filters per kind and lot, an events-per-6h chart, and CSV/JSON export.

The ERP events are **SAP-style, simulated, not a real SAP integration**. They use generic concepts and only movement types 101, 261 and 321, which are named on public SAP Learning pages (checked 1 Oct 2026):
- https://learning.sap.com/courses/inventory-management-and-physical-inventory-in-sap-s-4hana/posting-a-goods-receipt-with-reference (101)
- https://learning.sap.com/courses/implementing-sap-s-4hana-cloud-public-edition-manufacturing/executing-production-orders_eebd35c8-b7ed-4f36-bd4a-fb527dfa1322 (261)
- https://learning.sap.com/courses/inventory-management-and-physical-inventory-in-sap-s-4hana/performing-transfer-postings (321)

Document numbers are simulated sequence numbers. No SAP field names or transaction codes are used; a test restricts movement types to those three. Event texts live in the config (`events` per stage), so they can be changed without code.
