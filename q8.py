import sqlite3 #https://docs.python.org/2/library/sqlite3.html
import sys
import re

PREDICATE_URL = {}

def main():
    if len(sys.argv) != 3:
        print "Usage: python q8.py <database file> <RDF input file>"
        sys.exit()

    # database = sqlite3.connect(sys.argv[1])
    # cursor = database.cursor()

    infile = open(sys.argv[2], 'r')  # read the RDF data file
    input_lines = infile.readlines()
    infile.close()

    # parse_file(database, input_lines)
    parse_file("DEBUGGING WITHOUT DB", input_lines)

    # db.close()


def parse_file(db, lines):
    """
    parses lines of the file for insertion to the database
    param db: the database instance
    param lines: the list of lines read from RDF data file
    """

    for line in lines:
        # print line
        prefix = re.search("(?:prefix)(.*)", line) #TODO use regular expressions as much as possible for string manipulations
        #https://docs.python.org/2/howto/regex.html
        print prefix.group()
        break
        # line_contents = line.split('\t')
        # if line_contents[0] == ''
        # print line_contents

if __name__ == "__main__":
    main()
