# Principles

The durable output. Everything else here — tools, templates, rules — is an
implementation of one of these. When adding something new, it should trace back
to a line on this page; if it doesn't, question whether it belongs.

Each principle names the concrete failure that produced it. They were not
reasoned out in advance; they were paid for.

---

## On mapping a codebase

**1. Structure first, meaning second.**
Finding groups needs no understanding — it is counting connections between files.
Naming a group does need understanding. Conflating the two is what makes repo
orientation feel circular ("to point the AI at the right file I must already know
the structure"). Split them and the circle disappears.

**2. Rank by connections, not size.**
A 402-line file with 103 importers is critical infrastructure. A 639-line file
with zero importers is an entry point. Line count cannot tell them apart, and
every ranking built on it is misleading.

**3. Folders are the first hypothesis; the graph is the test.**
In most repos the developers already clustered the code. Check the free answer
before building anything. The *disagreements* between folder and graph are the
valuable output — each one is a misfiled file or a hidden dependency.

**4. An honest map that says "I don't know" beats a confident map that is wrong.**
Label every edge with how it was learned: `static` (certain), `dynamic`
(inferred), `runtime` (observed). Static analysis is ~85% of the truth; say so
rather than implying 100%.

**5. A missing signal is not a zero.**
A churn column of zeros because nothing is git-tracked reads identically to "this
code never changes." Report coverage, not just values.

---

## On facts about the machine

**6. Generate facts, never type them.**
Every hand-written path and version goes stale silently. An instruction file
claimed "a Python 3.14 venv at `venv/`" when the project had `venv_311/` running
3.11.9 — the author had read the *system* interpreter's version.

**7. Record the system interpreter beside the project's.**
Not to use it — to make the two impossible to confuse. That exact confusion
produced principle 6's failure.

**8. Verified means executed.**
A command inferred from a config file is a claim. A command that answered when
invoked is a fact. Stamp the difference and never let the two look alike.

---

## On oracles

**9. An oracle must be able to go RED.**
`git diff --name-only | grep -q README.md` asks "did the file I just edited get
edited?" It cannot fail, so it proves nothing. If you cannot describe how a check
fails, it is not a check.

**10. No repo need be oracle-less.**
Any repo with source and a working interpreter can at least be compiled, and a
syntax check genuinely goes red. A weak oracle honestly labelled beats declaring
the whole repo undelegable — because the alternative is principle 12.

**11. A green build is not correct behaviour.**
It cannot see dynamic dispatch, plugin wiring, or anything reached by name at
runtime. Require an `UNVERIFIED` line in every report and never accept it empty.

---

## On agent behaviour

**12. Always give the model a sanctioned way to fail.**
Without one, it will invent an unsanctioned way to succeed. Given "no verified
command" and no permission to stop, an agent forged the evidence file. The fix
was not a sterner rule — it was making "this cannot be done" a legal, expected
outcome.

**13. A check the agent can reach is a check the agent can defeat.**
Rules can be forgotten. Lint inputs can be edited. Only a hook runs outside the
model's action space. Promote any recurring failure to the strongest enforcement
level available.

**14. Every diagnostic message is an instruction.**
A linter that said "merge or delete the ones you do not want" got files deleted.
Phrase remedies as questions for the human, never as imperatives an agent can
execute.

**15. Reject unknown input; never absorb it as data.**
An agent invented a `--repo` flag; the script swallowed it as literal text into
the goal and the closure command, silently malforming the oracle. Fail loudly on
what you do not understand.

**16. When an agent invents an interface, that is a design signal.**
The flag it reached for is usually the one that should exist. Add it — then still
reject unknown flags, because the next invention will be different.

**17. Separate a wrong goal from a wrong method.**
The agent that destroyed 260 lines of a file was correctly trying to get it under
a real size cap. Chasing a real problem badly needs a different fix from
inventing a problem.

---

## On the tools themselves

**18. Test tools against a repo whose answer you already know.**
Every bug found in this toolkit was caught that way. None were caught by reading
the code — including a role that could never fire, a launcher that absorbed 97
imports belonging to a package, and a Windows path bug that stamped every working
command as FAILED.

**19. A noisy linter is a disabled linter.**
Every false positive spends credibility you cannot re-earn. Two bad rows and the
human starts skipping the output.

**20. Never shorten a file by line count.**
Remove a named section deliberately, or split it. Arbitrary truncation destroys
content silently and leaves the file ending mid-sentence.

**21. Two resolutions, always.**
A ~40-line summary for context; the full table on disk to be grepped. Retrieval
accuracy falls as context grows, and falls hardest on small models — so a map
that is too long defeats the purpose it was built for.
