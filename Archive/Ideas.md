# Principles

How I build code. One aim sits under every rule: **simplicity and maintainability, in service of the goal.**

---

## 0. The economics of code

Every line is a cost: something to read, test, explain and keep working. Lines are a liability, not an asset.
What has value is the problem solved.

- **The best code is the code you never write.** Every line is a place for something to break.
- **Work vs motion.** Work is the part of activity that moves toward the goal; the rest is motion.
  Code that isn't asked for, and that the important code ends up depending on, is motion with a maintenance bill.
- **Opportunity cost.** Every hour spent on one thing is an hour not spent on the bottleneck.
  Ask: *is this moving toward the problem in the quickest way?*
- **Attack the bottleneck.** Optimising anything else doesn't make you faster.
- **Don't optimise a process that shouldn't exist.**
- **Don't rebuild what exists.** Check for an existing tool, library or standard first.
- **Goal, not tools.** Meet a problem, then find the tool. Start with the tools and the tools become the goal.
- **The schema comes from the goal.** It's induced from how you want to create and query the data.
- **So what?** Every analysis connects to a decision, or it isn't finished.
- **Small and precise beats big and vague.** Something small and perfectly designed has more punching power,
  like pressure: less surface area, more force.
- **Occam's razor.** Don't add entities beyond what's needed.
- **Rule of least power.** Use the least powerful tool that does the job: SQL before Python for queries,
  the standard library before a dependency, a dict before a class, data before code.

The same lens applies everywhere: look at code and ask *what is it worth*, look at it and ask *what is the maths*.
Moving between domains (economics, maths, systems) is how a principle from one becomes a tool in another.

## 1. Anatomy of a program

A program is built from a few ingredients, combined. Each file should make them visible, in this order:

1. **Sets (types):** what kinds of things exist. *E.g. `SiteCode`, `Species`, `Reading`.*
2. **Data coming in:** where it crosses the boundary, and the type it becomes.
3. **Operations:** functions on those sets. Each one is small and does one thing.
4. **Composition:** the operations chained together. **That chain is the program.**

If a reader can list these four things for a file, they understand it.

## 2. Code as a proof

A proof starts from axioms and definitions, then moves forward one justified step at a time.

- **Lead with the maths.** Write the model (sets, functions, definitions) first; then put it in code.
  The code follows the model name for name. If the model is right and the code mirrors it, the result is right.
- **Axioms and definitions first.** Each name is defined once, in one place, at the top or in its own file.
- **Single logical jumps.** Each line and each function takes one step a reader can check alone.
- **Each file ends in one or two functions.** Everything above them exists to make them obvious.
- **Chain back to the axioms.** Trace any result back through its steps and they get simpler,
  until you reach the axioms. If you can't, a step is missing.
- **Assumptions are axioms at the boundary.** They describe data crossing from the world into the system.
  If one fails, the fault is in the axiom, not the code. State each one.
- **A grammar encodes the set.** A small set of definitions plus rules for combining them is lighter
  than listing every case.

## 3. A file is a state machine

Python runs a file top to bottom: a linear chain. Each definition extends what exists;
each function call moves the program from one state to the next.

- **Move from safe state to safe state.** A *safe state* is one where every invariant holds.
  Each function is a transition: it starts in a safe state and must end in one.
- **This is a Hoare triple** `{P} f {Q}`: if P holds before `f`, Q holds after.
  A pipeline is a chain of them: `raw → parsed → loaded`, with an invariant checked at each arrow.
- **Can't reach a safe state? Stop.** Raise an error that says what failed. Never return a guess (*fail fast*).
- **Tables are nodes, workflows are paths.** Data moving from table to table is a path through a graph of tables.
- **Map the nodes.** A node (function, definition, data structure) can hold its own smaller machine.
  Draw it when it isn't obvious.

## 4. Types and contracts at every boundary

- **Typed contracts across boundaries.** API → code, code → database, module → module:
  each crossing has a stated shape. A function's signature is its contract.
- **Parse, don't validate.** Turn raw input into proper types once, at the boundary;
  after that the types guarantee correctness.
- **Make illegal states unrepresentable.** Missing is `None`, never `0` or `""`.
- **Total functions.** Every input gets a correct value or a named error. No silent fallbacks.
- **Define equivalence.** To say two things are the same, first define the form you compare them in.

## 5. Pure functions, small functions

- **Pure functions.** Same input, same output, no side effects.
- **Functional core, imperative shell.** Pure logic in the middle; network, disk and database at the edges.
- **Tiny functions.** One job, a clear name, readable at a glance.
- **Complexity is conserved; design decides where it lives.** Spread it across many small functions
  so none is hard, and each can be refactored in place.
- **Contain the mess.** A change, a failure or an unfinished piece should stay local, never half-spread.

## 6. Macro mirrors micro

Principles from distributed systems, cloud computing and operating systems hold across the macro/micro boundary.
A single Python file can be designed like a distributed system, and a distributed system deserves the rigour of a
language and its types.

| Distributed system (macro) | Code (micro) | Shared principle |
|---|---|---|
| Service | Function or module | One job, behind an interface |
| API contract | Type signature | The interface is fixed; the inside is free to change |
| Message between services | Argument and return value | Data passes explicitly, not through shared state |
| Idempotent endpoint | Pure function | Twice is the same as once |
| Schema registry | Types defined once | One source of truth for shapes |
| Fail fast at the edge | Raise at the boundary | Bad data never travels inward |
| Atomic commit | Write to `.part`, then rename | Never leave a half-finished state |
| Immutable event log | Raw data kept untouched | Everything else can be rebuilt from it |
| Service graph, no cycles | Import graph, no cycles | Built and understood in order |
| Blast radius | Function scope | A failure or change stays local |

- **Each function is its own service:** a contract, an inside it owns, and a refactor changes nothing outside it.
- **Decouple errors from functions:** each function handles its own failure at its own boundary.
- **Loose coupling, high cohesion.**
- **Locality emerges.** If the structure is right, any one file can be read on its own.

## 7. Data structures, algorithms, graphs

- **Reduce to known structures.** Name the structure the problem already is (set, map, tree, graph,
  join, closure), then handle only what differs.
- **Quantify the qualitative.** Embed words and messy data in data structures, so problems reduce to
  problems with known solutions.
- **Files are nodes; imports are edges.** They point one way.
- **Trees and databases are the same picture.** A shared field is a join; chaining joins rebuilds the tree.
- **Pick the simplest structure that fits.** A set when order and duplicates don't matter; a dict for lookups;
  a table when it's relational.

## 8. Verification

- **Generation is cheap; verification needs a certificate.** With AI, writing code is easy;
  knowing it's right is the bottleneck. Keep code small and checkable.
- **A trusted model plus tests for it gives the code in between a certificate.**
- **Specification is the bottleneck.** Whatever you don't specify, the AI assumes.
- **Write claims as checks.** Each invariant is a line of code that fails loudly, not a comment.
- **Name the invariants** (I1, I2, …) and the mechanism that enforces each.
- **Reproducible.** Pinned dependencies; outputs are a pure function of the raw data.
- **Nothing public I can't explain.**

## 9. Rigour without paralysis

Rigour serves the goal; it doesn't replace doing.

- **Make it exist first, make it great later.** Elegance comes after the mess, not before.
- **Instances before abstracting.** Walk through concrete cases before generalising or automating.
- **Abstraction before work is a fallacy.** Seductive, but it stops work from happening.
- **Start manually.** The pain points show you the solution.
- **Worthwhile implies difficult, not the converse.** Difficulty alone is no sign of value.

## 10. Commits and explanations

- **Commits record decisions and reasons.** The history alone should tell the story.
- **Commits reduce work, not add it.** 1,000 commits no one understands are useless.
- **Explain as a chain:** code, then maths, then design choices, then findings, then motivation.
- **Show the picture first.** Draw structures before describing them.
- **Examples are concrete, real and complete:** raw input, logic and output, side by side.

---

## Concepts worth knowing

| Concept | One line |
|---|---|
| Hoare logic / design by contract | Preconditions and postconditions on every function |
| Invariant | A fact true in every safe state |
| Referential transparency | A call can be replaced by its result without changing meaning |
| Idempotency | Doing it twice equals doing it once |
| Total vs partial function | Defined for every input vs undefined for some |
| Parse, don't validate | Turn data into types once; trust the types afterwards |
| Functional core, imperative shell | Pure logic inside, side effects at the edges |
| Single source of truth | Each fact is stored or defined in exactly one place |
| Rule of least power | Choose the least expressive tool that does the job |
| Occam's razor | Don't add entities beyond necessity |
| YAGNI | "You aren't gonna need it": don't build for imagined futures |
| Normal forms (3NF) | Columns depend on the key, the whole key, nothing but the key |
| Topological sort | An order where everything comes after what it depends on |
