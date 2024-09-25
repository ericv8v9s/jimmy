# Proving Program Correctness

The idea of proving program correctness dates at least to the time of
Turing, and likely earlier given the mathematical nature of computer
science. In his 1949 short paper titled "Checking a large routine",
Turing discussed an example program for computing factorials by repeated
multiplication and presented an argument for its correctness and
termination. Similar work was also pursued by Floyd and Hoare, the
latter of which noted that:

> The cost of removing errors discovered after a program has gone into
> use is often greater, particularly in the case of items of computer
> manufacturer’s software for which a large part of the expense is borne
> by the user. And finally, the cost of error in certain types of
> program may be almost incalculable—a lost spacecraft, a collapsed
> building, a crashed aeroplane, or a world war. Thus the practice of
> program proving is not only a theoretical pursuit, followed in the
> interest of academic respectability, but a serious recommendation for
> the reduction of the costs associated with programming error.

Yet, despite continued academic research and the explosion of commercial
software complexity, formal methods are still sparsely employed in
practice. As Edgar and Alexei Serna concluded in their literature
review:

> [Formal methods] seem well developed and are supported by a large
> number of applications, users and important critical developments;
> however, as a limitation, they have ceased to be a major component in
> computer science and engineering training, few professors are working
> on them, course offerings at the undergraduate and graduate levels are
> scarce, they are difficult to apply in important projects, and only a
> small number of graduates welcome them as a source of work.

This limited project does not hope to produce a meaningful impact to the
grand technical and social challenge. Instead, it is aimed at the lesser
goal of gaining familiarity with existing theories and software relevant
to the field such that a foundation could be built for future work.


This project has the following objectives:

[x] Design and implement a simple language.
[x] Build a proof system.
[x] Implement an algorithm in the new language and prove its correctness.
[ ] Extending the language to implement procedures.
[ ] Extending the proof checker to support proofs about procedure calls.
[ ] Rewrite the proof system in the new language.
[ ] Prove the correctness of the proof system.
