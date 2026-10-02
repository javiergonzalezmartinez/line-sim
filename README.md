# line-sim

Discrete-event simulator of a serial production line with finite buffers, random failures and blocked/starved accounting. Python standard library only.

    python3 -m linesim examples/line.json --out report.html
    python3 -m unittest discover -s tests -t .

The example line is fictitious and illustrative. It does not describe any real plant.

## What you learn here
Why a line runs below its slowest station: blocking and starving, failures, and what a buffer is worth. Buffer size 0 (direct hand-off, the finished part waits in its station) is modelled in linesim; the plant view still clamps to 1.

## Whole-plant model (plantsim)
Batch flow of a fictitious oral-solid-dose plant, warehouse receipt to dispatch: receipt and quarantine, QC sampling and release (day shift), dispensing, granulation, compression, coating, packaging, QC lab release (retests), QA record review, dispatch waves. Changeover and cleaning when the product changes, breakdowns, working calendars.

    python3 -m plantsim examples/pharma.json --view plant.html

`plant.html` is an offline interactive 2D view: floor-plan layout, lots as moving entities, forklifts as a shared resource pool, live charts (lots in the plant, cumulative finished, utilisation) and a parameter panel (release rate, servers per stage, forklifts, transport time, breakdowns, changeovers, 24/7 labs). Changing a parameter re-runs the simulation in the browser with `plantsim/engine.js`, a port of the Python model.
Use `examples/pharma_flow.json` for the material flow (dock, warehouse quarantine, dispensing, intermediate store, production, finished-goods hold, shipping) with forklift transport. Deep links: `#t=381&s=0.5&fk=1&mv=6` = start time, speed, forklifts, transport multiplier.

Tests: `python3 -m unittest discover -s tests -t .` and `node --test tests/`. The JS engine is checked against Python: identical completion times with randomness off, means within 3% over 20 seeds with randomness on.

Not modelled yet: finite buffers between stages, stock-level based material shortages, deviations and QA holds beyond a retest chance, campaign sizing. All numbers are invented and illustrative.

## Signal and transaction layer
Every simulated lot generates PLC/sensor events (dock door, barcode scans, scales, conveyors, palletizer states, labelling, serialization, forklift RFID), WMS events (goods receipt, putaway and transfer orders, bin status), QA/LIMS events and ERP events (goods receipt, quarantine to unrestricted release, goods issue to production order, operation confirmations, backflush, outbound delivery and goods issue). The page shows a live log with filters per kind and lot, an events-per-6h chart, and CSV/JSON export.

The ERP events are **SAP-style, simulated, not a real SAP integration**. They use generic concepts and only movement types 101, 261 and 321, which are named on public SAP Learning pages (checked 1 Oct 2026):
- https://learning.sap.com/courses/inventory-management-and-physical-inventory-in-sap-s-4hana/posting-a-goods-receipt-with-reference (101)
- https://learning.sap.com/courses/implementing-sap-s-4hana-cloud-public-edition-manufacturing/executing-production-orders_eebd35c8-b7ed-4f36-bd4a-fb527dfa1322 (261)
- https://learning.sap.com/courses/inventory-management-and-physical-inventory-in-sap-s-4hana/performing-transfer-postings (321)

Document numbers are simulated sequence numbers. No SAP field names or transaction codes are used; a test restricts movement types to those three. Event texts live in the config (`events` per stage), so they can be changed without code.

## Deeper model (stage 3)
- **Transport from layout distance**: `m_per_px`, `speed_kmh`, `handling_min` in the config. A leg takes Manhattan distance between area centres divided by forklift speed, plus handling (load and unload). No traffic, turning or battery model.
- **QA holds and deviations**: stage kind `hold` (probability `p`, duration, QA calendar, `reject_p`). Rejected lots leave the plant and do not count as throughput; the page shows them and the log records the deviation, the hold and the rejection. The example rates are illustrative and set high enough to be visible.
- **FEFO vs FIFO**: raw-material lots get a simulated shelf life; each dispensing picks from released, unconsumed lots by earliest expiry (FEFO) or earliest release (FIFO). The page counts the picks where the two rules differ. Tested against an independent brute-force recomputation.
- **MQTT-style message view**: each signal can be shown as a topic and JSON payload (`fictitious-plant/<area>/<device>`, invented naming), exportable as JSON lines. No broker or real protocol is involved.
- **Palletizer detail**: pattern (5 layers x 12 cases), robot pick and place per layer, pallet complete with case count.
Still not modelled: finite buffers and blocking between stages, stock-level based material shortages, AGV traffic, real OPC UA/MQTT/IDoc interfaces.

## Milestone 6: finite buffers and blocking (illustrative)

A process or move stage can have `buffer`: the maximum number of lots waiting in front of it (absent = unlimited). When any stage has a buffer, an event-driven engine runs (`simulate_des` in Python, `simulateDES` in `plantsim/engine.js`). Without buffers the old engine runs unchanged.

- Semantics: block-after-service. A finished lot stays on its resource (machine or forklift with the pallet) until the next stage has room. Blocked lots are released in FIFO order.
- Cross-checks: with no blocking the new engine gives the same times as the old one for every lot; lots are conserved; JS and Python match on times, blocked hours and max queue; buffer limits are never exceeded (see tests).
- Example `examples/pharma_buffers.json`: 7.9 batches/week and 8.83 days lead time, against 7.7 and 9.01 without buffers (single run, illustrative). Most blocked resource-hours are forklift moves holding a pallet.
- Learn: with finite buffers, forklifts blocked holding pallets become a hidden bottleneck.
- Limits: no AGV path conflicts, material availability is a simple chance of a wait per lot (`shortage_p`, `shortage_hours` on process stages: the resource waits idle), no stock levels or purchase orders; no shift-level staffing (a stage can have daily `breaks` gaps: `"breaks": [[6,6.5]]` = no new lot starts 06:00-06:30; a running lot is not interrupted), wave and hold stages have no capacity limit (a wait stage can have one: `"capacity": N`, modelled as N resources, shown as a process in the view), nothing validated against a real plant. In the view, buffer size change below 1 is clamped to 1.

## Event log (milestone 11)

`python -m plantsim examples/pharma_flow.json --events events.jsonl` writes the simulated run as canonical events (EPCIS-style fields: class, type, action, event/record time, correlation and causation ids, sequence number, object ids, result, payload hash). `examples/canonical-event.schema.json` is the schema provided by Javi (synthetic / anonymised digital-twin spec); `plantsim/events.py` validates events against the subset of JSON Schema it uses, with no external library. Ids are pseudonyms (LOT-000001, EQ-STAGE-03) on a fixed synthetic start date. The tables of the spec (state machines, signals, KPIs, handshakes, failures, parameters) are in `spec/*.json`; parameters marked TBD there stay TBD. Not a real MES or historian, not validated against a real plant.

### State machines (milestone 12)

`plantsim/fsm.py` loads the transition tables from `spec/state_machines.json` (8 machines). An event is allowed only if the table has a row for that machine, state and event; otherwise `IllegalTransition` is raised, the state is kept and the attempt is logged. The event log now drives JOB_ORDER (one per lot) and PHASE_EXECUTION (one per lot and stage); each such event carries `state_before_hash`, `state_after_hash` and the transition in `reason_code`. Not yet driven: machine item/operation mode, handling unit, transport task, quality status and message machines (the tables are loaded and tested). Guards in the spec are text and are not evaluated.

### Machine telemetry (milestone 13)

`python -m plantsim examples/pharma_flow.json --telemetry tele.jsonl` writes sensor events (state-change sampling) for every process/move stage: item_state (SIG-0001), operation_mode (SIG-0002), cycle_counter (SIG-0003), operating_time in seconds (SIG-0004) and, for single-server stages, job_id (SIG-0010). They are driven by the MACHINERY_ITEM_STATE and MACHINERY_OPERATION_MODE machines from the spec and validate against the canonical schema. A stage with several servers is treated as one equipment (EXECUTING while at least one server works). Not produced because the simulation has no basis for them: power, safety, fault, alarm, speed, temperature and other process values; signal quality is always GOOD; the SETUP mode is not used (changeover is not traced per equipment). Synthetic, not a real historian or OPC UA.

### KPIs from the event log (milestone 14)

`python -m plantsim examples/pharma_flow.json --kpis kpis.html`. `plantsim/kpis.py` computes, from the events only: throughput (KPI-001), lead time (002), cycle time per stage (003), queue wait per stage (004), time-average WIP (005), utilisation per stage as time executing (006), sensor good-quality share (018, 100% by construction) and scrap rate on a lot basis (026). Tests compare them with the simulator's own numbers: throughput, lead time, scrap count and utilisation agree (timestamps are rounded to milliseconds); queue wait agrees for stages without changeover, and is larger by the changeover time where there is one, because the traced start is after the changeover. Not computed, no basis in the log: blocking, starvation, setup fraction, downtime, first-pass yield, rework, inventory, messages and the GxP KPIs.

## M15: interface handshakes and seed scenario (synthetic)

`python3 -m plantsim examples/seed_scenario.json --messages out.jsonl` emits HS-001 MOVE_REQUEST message events (sent, timeout/rejected, retry, acknowledged, reconciled, dead-lettered, duplicate discarded) on the MESSAGE state machine, validated against the canonical schema. KPI-015/016/017 are computed from them.

- Parameters (ack latency, timeout, loss, nack, duplicate, retries) come only from the `handshake` key of the config. The spec leaves them TBD, so with no config the handshake is ideal (100% success, zero latency). The values in `examples/seed_scenario.json` are illustrative.
- Failure catalogue: FME-009/013 (timeout), FME-011 (duplicate), FME-014 (rejection) are modelled; FME-016 is the existing `breakdown_p`. The other failure modes in `spec/failures.json` are NOT modelled.
- `examples/seed_scenario.json`: capacities and equipment ids from the synthetic seed; every time is an illustrative placeholder. 1 lot stands in for 1 handling unit.
- Not a real SAP or MES integration. Synthetic data only.
