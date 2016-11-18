import sqlite3
import sys

PREFIX = {}
STATE = {'IN_PREFIX': False,
         'IN_SELECT': False,
         'IN_WHERE': False}


def main():
    if len(sys.argv) != 3:
        print("Usage: python q8.py <database file> <SPARQL query file>")
        sys.exit()

    infile = open(sys.argv[2], 'r')  # read the SPARQL query file
    input_lines = infile.readlines()
    infile.close()

    query = parseFile(input_lines)

    conn = sqlite3.connect(sys.argv[1])  # connection to the database
    c = conn.cursor()  # cursor

    c.execute(query)
    print(c.fetchall())


def parseFile(sparql_lines):
    """
    parse the SPARQL query, translate and return it as an sqlite query
    :param sparql_lines: a list of each line in the SPARQL query file
    :return: a string cotaining sqlite query
    """
    for line in sparql_lines:
        line = line.strip()
        if line == "":  # if the line is blank, go to next line
            continue
        line = line.split()

        if line[0].upper() == "PREFIX":
            STATE['IN_PREFIX'] = True
            PREFIX[line[1][:-1]] = line[2][1:-1]
        elif line[0].upper() == "SELECT":
            STATE['IN_PREFIX'] = False
            STATE['IN_SELECT'] = True
            for



if __name__ == "__main__":
    main()
