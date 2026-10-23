## 1. Explore and model the API

The first step is to explore and model the API and understand the data we have access to.

### Definitions
- **Endpoint:** the API has many URLs. Each one is an endpoint that returns a particular set of data.
- **Connect:** work out which fields let you link results from one URL to another.
  - Connecting means joining the tables on these shared keys.
  - The shared key is what matches a row in one table to the relevant row in another.

### Modelling the API formally and mathematically
- **Formal model:** define sets, high-level structures, data types, etc.
- **Mathematical model:** create a faithful representation of the data.
  - This touches on representation theory and related mathematics.
  - In plain terms: take the data, turn it into numbers, and do maths with those numbers in a way that preserves the meaning and semantics of the data.
- **Visual model:** produce a visual representation of the pipeline to make it easier to understand.

## 2. Choose an angle

- Explore the data and semantics of the API so we can choose an angle: a subset of the data to focus on.
- From that, understand:
  - the audience
  - the insights we want to derive
- Let the problem pick the data and tools (see Guiding Principle below).
- Work backwards from the goal and the problem to pick the data.
- The result should be a clean, consistent, well-shaped data model and database that we can run analyti

## 3. Checklist (requirements)

### Pipeline
- The pipeline pulls data and only adds new data.
- It must run cleanly and only add new data (idempotency).

### History
- Collect history over time: run the pipeline repeatedly and leave a trail of our work.

### Angle and audience
- There must be an angle and an audience.
- Relate it to current world events:
  - The end goal is to generate business value and revenue.
  - A project done out of context is less impactful than one done in the context of what's currently happening.
  - Ask: *how can the pipeline be used to solve a real problem?*
  - Possible scope: the climate crisis, which is causing storms and similar events, I believe especiall

### Data model
- Know how the data model works and how to extend it.

### Personality
- For me, this is: **maths, business, rigour, beauty, simplicity, the rule of least power**, and meta-cproach the project.
- Think about the experience a senior engineer would bring: the laws and principles that can only reall.
- Start from those principles so that we eliminate entire classes of errors, misuse, etc.

### Explanations
- Clear explanations throughout.

## 4. Development loop

- Commit our thoughts, decisions and rationale.
- Anything committed should be legible and intelligible.
  - 1,000 commits that no one understands are useless.
- Commits should reduce work and pain, not increase it.
- They should not create more surface area to understand.
- They should almost replace the need to read every line of code.

## 5. Guiding principle

**The problem or goal should pick the data that it requires and that serves it. The data shouldn't pick**

- If you look at the data and ask "what can I answer?", you may answer something no one wants answered
- Starting from the problem keeps the work directed at something valuable the entire time.