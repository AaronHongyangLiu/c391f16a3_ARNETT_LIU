Aaron Liu and Taylor Arnett


Question 2:
    - assume that all the international airports have the word "International" in their name


For both q8 and q9, please make sure you are running with python2. Ideally python 2.7.10, but 2.7.6 will work too.

Question 8:
    - assume that the database file inputted in the program already has its schema built with the SQL commands in both q6.txt and q7.txt
    - assumes RDF input data where each object is on a new line, and if there are multiple predicates separated by ';', then the new predicate is also on a new line. The example Edmonton.txt file is an example of this.
    - assume that there is at least a space between the end-line token and the rest of the triples on the line

    To run q8:
        python q8.py <database file> <RDF input file>

Question 9:
    - assume that the SELECT and ?var will be in the same line
    - assume there is no || or &&
    - assume that the object with URI are not treated as numbers so they will not be shown when using numerical constraints.
        For example: "123.0"^^ns35:inhabitantsPerSquareKilometre will be treated as a string with a special type, and cannot be accessed with a filter like FILTER(?var > 0).

    To run q9:
        python q9.py <database file> <SPARQL query file>