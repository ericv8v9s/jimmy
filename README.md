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

This project implements a method of proving program correctness
up to certain desired properties by evaluating with placeholder values
and tracking properties between such values.
