# A Project to Design and Implement a Simple Language, and to Formally Verify the Correctness of Programs Written in Said Language

In the words of C. A. R. Hoare:

> The cost of removing errors discovered
> after a program has gone into use is often greater,
> particularly in the case of items of computer manufacturer's software
> for which a large part of the expense is borne by the user.
> And finally, the cost of error in certain types of program
> may be almost incalculable—a lost spacecraft, a collapsed building,
> a crashed aeroplane, or a world war.
> Thus the practice of program proving is not only a theoretical pursuit,
> followed in the interest of academic respectability,
> but a serious recommendation for the reduction of the costs
> associated with programming error.

Since the standard practice of software engineering today
does not include proofs of programs,
it is no secret that the decades since have shown,
in most circumstances,
programmers and their programs are just fine without the help of formal methods
by relying on testing as in any other trade of engineering.
However, in cases where the risk is great and correctness must be guaranteed
— such as desired by the highest Evaluation Assurance Level, EAL7 —
formal verification remains the only option.
This project experiments with the application of one of such formal methods.
It is expected to progress in the following phases:

1. Design and implement a simple language.
2. Build a proof system.
3. Implement an algorithm in the new language and prove its correctness.
4. Rewrite the proof system in the new language.
5. Prove the correctness of the proof system.

The language will be minimal in functionality so as to reduce complexity.
Currently, only the following features are expected:

- integer arithmetic
- boolean operation
- variable & assignment
- `if` conditional
- `while` loop

These operations all have corresponding axioms in Hoare logic,
which will be the basis for proving programs composed of these constructs.
A possible extension would be the addition of pure functions and/or subroutines.

The language will be interpreted.
Performance and compiler design are specifically non-goals.
Phase 1 is expected to be relatively easy.
In fact, a parser for the language is already completed at the time of writing.

The proof system will be responsible for verifying each deduction step
and recording the completed proofs.
Beyond the axioms that needs to be built-in,
the system must also keep track of a library of theorems,
which is to be extended or otherwise manipulated by the user.

Proofs are produced manually: the system exists mostly for checking proofs.
Ideally, proofs are also produced interactively,
with the user specifying the theorem to apply
and the system applying then possibly simplifying the proposition in question.
However, automated reasoning is specifically a non-goal.
Further, interations with the system will be text based
(through files or standard input)
and the implementation of graphical user interfaces is a non-goal.
Phase 2 is most risky as
the implementation of such as system (even without interactivity)
may turn out to be complex.

Once the first two phases are complete,
an existing algorithm (such as insertion sort)
will be implemented in the new language and formally verified.
Phase 3 should be relatively easy,
except the task of producing the proof may be tedious
since the proof system will initially contain only the axioms.

Phases 4 and 5 are considered optional,
and will only be pursued if time permits.
