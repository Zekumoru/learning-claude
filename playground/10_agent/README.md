# 10 — Agents and Workflows

This section is mostly **theory**: a vocabulary for the two broad strategies you reach
for when a task can't be done in a single Claude request, plus a small catalog of
reusable **workflow patterns**. This README captures the concepts from all the
lectures in the section — the intro, **parallelization**, **chaining**, **routing**,
**agents + tools**, **environment inspection**, and the closing **workflows vs. agents**
wrap-up.

---

## The one distinction that matters: workflow vs. agent

Both are ways to solve a task that needs **more than one call** to Claude. The line
between them is **how well you understand the task ahead of time.**

- **Workflow** — *you* know the exact steps. A workflow is a series of Claude calls
  arranged in a **predetermined sequence** that you write out in code. You're in
  control of the flow; Claude fills in the intelligent parts of each step.
- **Agent** — you *don't* know the exact steps. You hand Claude a **goal and a set of
  tools** and let it decide how to reach the goal. Claude is in control of the flow;
  you supply the capabilities and the objective.

A quick test:

| If you can… | …use a |
| --- | --- |
| picture the exact flow / steps in advance | **Workflow** |
| constrain users to a fixed set of tasks (the UX dictates the steps) | **Workflow** |
| *not* predict what task or parameters you'll be handed | **Agent** |

A useful realization from the lecture: **you've already been building both.** Every time
you gave Claude tools and let it figure out how to finish a task, that was an agent.

> Identifying a pattern doesn't *do* anything on its own — you still write the code that
> implements it. The value of naming these patterns is that they're **repeatable
> recipes**: solutions other engineers have found reliable, ready to apply to your own
> features.

---

## Pattern: Evaluator–Optimizer (the producer/grader loop)

The lecture's worked example is an **image → CAD** workflow: a user drops in a photo of a
metal part and the app produces a STEP file (a standard 3D model format). Because we know
*exactly* what to do with an image, it's a clean workflow:

1. Feed the image to Claude → ask it to **describe** the object.
2. From the description → ask Claude to **model** it with the CadQuery library.
3. **Render** the model.
4. Ask Claude to **grade** the rendering against the original image. If it's wrong, feed
   the problems back and try again.

Step 4 is the pattern. **Evaluator–Optimizer** has four moving parts:

- **Producer** — takes input, creates output (Claude modeling the part + rendering it).
- **Grader** — scores the output against some criteria.
- **Feedback loop** — if the grader rejects it, the critique goes back to the producer.
- **Iteration** — repeat until the grader accepts (or you hit a cap).

Use it whenever output quality is checkable but not guaranteed on the first try.

---

## Pattern: Parallelization (split → run concurrently → aggregate)

**The problem it solves:** one prompt asked to weigh many considerations at once does each
of them worse. The lecture's example is a **material recommender** — pick metal, polymer,
ceramic, composite, elastomer, or wood for an uploaded part. Cramming every material's
criteria into a single mega-prompt forces Claude to juggle all of them simultaneously,
which muddies the result.

**The fix:** break the one decision into independent sub-evaluations, run them at the same
time, then combine.

1. **Split** the task into focused sub-tasks — one per material, each with its own
   specialized criteria.
2. **Run in parallel** — send the same image to Claude N times concurrently, each request
   evaluating exactly one material.
3. **Aggregate** — feed all the individual analyses back into a final Claude call that
   compares them and makes the recommendation.

The sub-tasks **don't have to be identical** — each can have its own prompt, tools, or
criteria. That's the source of the benefits:

- **Focused attention** — Claude reasons about one material at a time, more thoroughly.
- **Independent optimization** — a weak metal analysis can be tuned without touching the
  others.
- **Easy scaling** — adding a material is just one more parallel branch, not a rewrite.
- **More reliable** — less cognitive load per call → more consistent output.

**When to reach for it:** a complex decision that decomposes into *independent* evaluations
— multiple criteria, several options to compare, or distinct domains of expertise. The key
requirement is that each branch can stand alone and contribute a distinct piece.

---

## Pattern: Chaining (split → run in sequence)

Where parallelization fans *out*, chaining goes *in order*. A chaining workflow breaks a
large task into **smaller sequential sub-tasks that build on each other**, instead of one
prompt doing everything.

The lecture's example is an auto-posting social media tool:

1. Find trending topics on Twitter.
2. Pick the most interesting one (Claude).
3. Research it (Claude).
4. Write a short-form video script (Claude).
5. Generate the video (AI avatar + TTS).
6. Post it.

Why chain instead of one big prompt:

- **Focus** — one specific task per call; Claude does each well instead of balancing all
  of them.
- **Non-LLM steps in between** — you can do ordinary processing or validation between
  links (steps 1, 5, and 6 above aren't Claude calls at all).
- **Sequential, non-parallelizable** work — each step needs the previous step's output, so
  it's the natural complement to parallelization.

### The "long prompt" problem — chaining's killer use case

When you give Claude content rules — *don't mention you're an AI, no emojis, no clichés,
professional technical tone* — a single prompt will often **still violate some of them**.
You get an article that sneaks in an emoji or a casual aside.

The fix is a **two-step chain**:

1. **Generate** — send the initial prompt and accept the first draft may break some rules.
2. **Revise** — send that draft back with a targeted cleanup instruction:

   > Revise the article below. 1. Remove any place the text identifies the author as an
   > AI. 2. Find and remove all emojis. 3. Replace any cringey writing with text a
   > technical writer would produce.

It works because the second call **only does revision** — it isn't simultaneously trying to
*create* the content and *police* the constraints.

**When to reach for it:** complex tasks with many requirements; cases where Claude keeps
dropping constraints in a long prompt; when you need to validate or transform output
between steps; or any time keeping each interaction focused improves the result.

---

## Pattern: Routing (categorize → dispatch to one specialized pipeline)

Parallelization and chaining both *decompose one task*. **Routing** does something
different: it **picks which pipeline a request goes to** in the first place. The premise
is that **different kinds of request need different handling**, and a single
one-size-fits-all prompt can't serve all of them well.

The lecture's example is the same social-media script tool. A user topic of `"programming"`
wants **educational** content — clear explanations and definitions. `"surfing"` wants
**entertainment** — high-energy, visual, exciting. One generic prompt does neither justice.

The fix is two steps:

1. **Categorize** — send the user input to Claude and ask it to classify into one of your
   predefined categories.
2. **Specialized processing** — use that category to select the matching prompt template
   (or workflow, or tools) and generate the real output.

So for `"Python functions"` you first ask:

```
Categorize the topic of a video into one of the listed categories:
<topic>Python functions</topic>

<categories>
- Educational
- Entertainment
- Comedy
- Personal vlog
- Reviews
- Storytelling
</categories>
```

Claude returns `Educational`, and you then run the educational template to write the script.

### Architecture

- User input hits a **router** component first.
- The router does an **initial Claude call** to categorize it.
- Based on the category, the input is **forwarded to exactly one** downstream pipeline.
- Each pipeline has its own prompts / workflow / tools, optimized for that category.

**The key insight:** input goes to **one** specialized pipeline, not all of them (that's
what separates routing from parallelization, where the *same* input fans out to many). One
destination is precisely what lets each pipeline be highly tuned for its case.

**When to reach for it:** your app handles **diverse** request types needing different
approaches; you can define categories that cover your cases; Claude can do the
categorization reliably; and the payoff from specialized handling beats the cost of the
extra routing call. It shines in customer-service bots, content generators, and anything
where the right response depends on first understanding *what kind* of request it is.

---

## Agents: tools make the agent

Everything above is a **workflow** — *you* lay out the steps. An **agent** is the other
half of the section's core distinction: you give Claude a **goal and a set of tools** and
let *it* decide how to combine them. You build the agent once, confirm it works
reasonably, and deploy it against a wide range of problems you didn't enumerate in advance.
The trade-off (explored later) is **reliability and cost** — flexibility isn't free.

### The power is in *combining* simple tools

An agent's capability comes from Claude chaining small tools in ways you didn't script.
Take three datetime tools:

- `get_current_datetime` — the current date/time
- `add_duration_to_datetime` — add time to a date
- `set_reminder` — create a reminder for a specific time

The same three tools answer wildly different requests by being combined differently:

| Request | Tools Claude chains |
| --- | --- |
| "What's the time?" | `get_current_datetime` |
| "What day is it in 11 days?" | `get_current_datetime` → `add_duration_to_datetime` |
| "Remind me about the gym next Wednesday" | all three in sequence |

Claude also recognizes when it's **missing information**: asked "When does my 90-day
warranty expire?", it knows to ask for the purchase date before computing the answer.

### Tools should be *abstract*, not hyper-specialized

The key design insight: give Claude **general, flexible** tools, not narrow one-off ones.
**Claude Code** is the model example — it ships with generic primitives:

`bash`, `read`, `write`, `edit`, `glob`, `grep`

…and *no* `refactor_code` or `install_dependencies` tool. Claude composes the primitives to
accomplish those higher-level tasks itself, which lets it handle countless scenarios the
developers never explicitly planned for. Specialized tools would cap the agent at exactly
the cases you anticipated; abstract tools let it improvise.

### Best practice: combinable tools

Design for combination. A social-media video agent might expose:

- `bash` — FFMPEG for video processing
- `generate_image` — create images from prompts
- `text_to_speech` — turn text into audio
- `post_media` — upload to platforms

That set supports both a simple straight-through flow (create → post) **and** an
interactive one — generate a sample image, get the user's approval, then proceed. Adapting
mid-task to user feedback is exactly what a rigid workflow can't do, and it's what makes
agents powerful for **dynamic, user-responsive** applications.

---

## Environment inspection: let the agent *see*

An agent built only of tools is still **blind**. Claude can't intrinsically know what an
action did — clicking a button might navigate, open a menu, or change nothing. The
companion to "give it tools" is **let it observe the results of using them.** This is the
piece that's easy to overlook and the difference between a blind command-executor and an
agent that adapts.

The clearest example is **computer use**: after every action (typing, clicking), Claude
immediately gets a **screenshot** so it can see the new state. That feedback isn't a
nicety — without it Claude has no way to tell whether the action succeeded.

### Read before you write

The same principle governs file work: **before modifying a file, read it.** Asked to add
a route to a Python file, Claude first reads the existing code to understand the structure,
then makes the change without breaking what's there. (This is also why Claude Code's own
tooling reads a file before editing it.)

### Guide inspection through the system prompt

For complex tasks you instruct the agent to inspect, right in the system prompt. A video
agent generating content with FFmpeg might be told to:

- run `whisper.cpp` to generate timestamped captions and **verify dialogue placement**,
- use FFmpeg to **extract screenshots** at intervals and visually check the output,
- **compare** the result against the original requirements.

### Why it pays off

Inspection buys you **progress tracking** (how close am I?), **error handling** (catch and
correct surprises), **quality assurance** (verify before declaring done), and **adaptive
behavior** (adjust based on what's observed).

### The design question to always ask

> **"How will Claude know if this action worked?"**

For every tool you give an agent, provide a way to observe its effect — read file contents
before edits, screenshot after UI actions, check API responses for the expected data,
validate generated output against requirements. Pair every *action* with a way to *see*.

---

## Workflows vs. agents: which to reach for

The section opened with this distinction and closes by making it a **decision**. Both
exist to handle tasks too big for one call; they differ in **who plans the steps**.

- **Workflow** — a predefined series of Claude calls for a *known* problem. You picture
  the flow ahead of time and break the big task into small, single-focus subtasks.
- **Agent** — Claude gets basic tools and *formulates its own plan*. You don't know the
  exact tasks in advance, so the system must be adaptive.

| | Workflows | Agents |
| --- | --- | --- |
| **Strengths** | One subtask at a time → higher accuracy; easy to test/evaluate (you know each step); predictable, reliable; great for well-defined problems. | Flexible UX; combine tools in unexpected ways; handle novel, unanticipated situations; can ask the user for more input. |
| **Weaknesses** | Inflexible — locked to specific task types; more constrained UX (you must know the exact inputs); more upfront planning. | Lower task-completion rate; hard to instrument/test/evaluate (you don't know the step sequence); less predictable. |

### The recommendation

> Your job as an engineer is to **solve problems reliably.** Users don't care that you
> built a fancy agent — they want something that works consistently.

So the default is: **implement a workflow wherever you can, and reach for an agent only
when one is truly required.** Workflows give you the reliability and predictability most
production apps need; agents trade some of that away for flexibility you only need when the
requirements genuinely **can't be predetermined**. Well-defined process → workflow.
Unpredictable, varied requests needing creative problem-solving → agent.

---

## Cheat-sheet

| Concept | One-liner |
| --- | --- |
| **Workflow** | You know the steps → predetermined sequence of Claude calls, you control the flow. |
| **Agent** | You don't know the steps → give Claude a goal + tools, it controls the flow. |
| **Evaluator–Optimizer** | Producer makes output, grader checks it, loop until accepted. |
| **Parallelization** | Split into *independent* sub-tasks, run concurrently, aggregate. |
| **Chaining** | Split into *sequential* sub-tasks; each builds on the last; non-LLM steps allowed between. |
| **Routing** | Categorize the input first, then dispatch it to *one* specialized pipeline. |
| **Long-prompt fix** | Generate first, then a second focused call to enforce the constraints. |
| **Agent** | Goal + abstract, combinable tools; Claude decides how to chain them. |
| **Abstract tools** | Prefer `bash`/`read`/`edit` over `refactor_code` — composability beats specialization. |
| **Environment inspection** | Pair every action with a way to observe its result; ask "how will Claude know it worked?" |

The throughline: **don't make one prompt do too much.** Parallelization and chaining
decompose a *single* task — *out* (independent, concurrent) and *forward* (dependent,
sequential) — while routing decides *which* task pipeline a request belongs to in the
first place. Evaluator–optimizer adds a feedback loop on top of any of them. And the
section's bottom line: **prefer a workflow for its reliability; reach for an agent only
when the task genuinely can't be predetermined.**
