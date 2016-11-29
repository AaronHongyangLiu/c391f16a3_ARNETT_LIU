Aaron Liu and Taylor Arnett


Question 2:
    - assume that all the international airports have the word "International" in their name


For both q8 and q9, please make sure you are running with python2. Ideally python 2.7.10, but 2.7.6 will work too.

Question 8:
    - the program assumes RDF input data where each object is on a new line, and if there are multiple predicates separated
        by ';', then the new predicate is also on a new line. The example Edmonton.txt file is an example of this.

Question 9:
    - assume that the SELECT and ?var will be in the same line
    - assume there is no || or &&
    - assume that the object with URI are not treated as numbers so they will not be shown with numerical comparison
        queries.
        For example: "123.0"^^ns35:inhabitantsPerSquareKilometre will be treated as a string with a special type, and
         cannot be accessed with a filter like FILTER(?var > 0).

