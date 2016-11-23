import sqlite3
import sys

PREFIX = {}
OUTPUT_VAR = []
STATE = {'IN_PREFIX': False,
         'IN_SELECT': False,
         'IN_WHERE': False,
         'IN_FILTER': False}
SUB_QUERIES = []
SUB_VARS = []
FILTERS = {}


def main():
    if len(sys.argv) != 3:
        print("Usage: python q8.py <database file> <SPARQL query file>")
        sys.exit()

    infile = open(sys.argv[2], 'r')  # read the SPARQL query file
    whole_file = infile.read()
    infile.close()

    input_lines = reformat(whole_file)
    query = parseFile(input_lines)

    print(query)

    # conn = sqlite3.connect(sys.argv[1])  # connection to the database
    # c = conn.cursor()  # cursor
    #
    # c.execute(query)
    # print(c.fetchall())


def reformat(string):
    """
    change the format of file so that:
      1. "SELECT" and "WHERE" will be in different lines
      2. (subj pred obj) and "WHERE {" will be in different lines
      3. there will be at least one space between SELECT and first ?var or *
      4. there will be at least one space between WHERE and {
    :param string: all the characters in the input file
    :return: a list of each line in the formatted file
    """
    # TODO: remove comments?
    # TODO: will the select and ?var in different lines?

    select_index = string.upper().index("\nSELECT") + 6
    string = string[:select_index + 1] + " " + string[select_index + 1:]  # changes #3

    where_index = 0
    while where_index < select_index:
        where_index = string.upper().find("WHERE", where_index + 1) + 4
    curly_open = string.find("{", where_index)
    string = string[:where_index - 4] + "\nWHERE {" + string[curly_open + 1:]  # changes #1,#2,#4
    return string.split("\n")


def parseFile(sparql_lines):
    """
    parse the SPARQL query, translate and return it as an sqlite query
    :param sparql_lines: a list of each line in the SPARQL query file
    :return: a string containing sqlite query
    """
    for line in sparql_lines:
        line = line.strip()
        if line == "":  # if the line is blank, go to next line
            continue
        line = line.split()

        if line[0].upper() == "PREFIX":
            STATE['IN_PREFIX'] = True
            if len(line) == 3:  # if there are spaces between ':' and <url>
                PREFIX[line[1][:-1]] = line[2][1:-1]
            elif len(line) == 2:  # if there's no space:
                index_of_colon = line[1].index(":")
                PREFIX[line[1][:index_of_colon]] = line[1][index_of_colon + 2:-1]
            else:
                print("Unexpected error when reading prefix line with tokens:", line)
                sys.exit()

        elif line[0].upper() == "SELECT":
            STATE['IN_PREFIX'] = False
            STATE['IN_SELECT'] = True
            for token in line:
                if token.upper() == "SELECT":
                    continue
                elif "*" in token:
                    OUTPUT_VAR.append("*")
                    break
                elif "?" in token:
                    OUTPUT_VAR.append(token[1:])  # add the ?var into the outputVar list
                else:
                    print("Unexpected error when reading ?var in SELECT line with tokens:", line, "token:", token)
                    sys.exit()

        elif line[0].upper() == "WHERE":
            STATE['IN_SELECT'] = False
            STATE['IN_WHERE'] = True

        elif STATE['IN_WHERE']:
            if line[0][:6].upper() == "FILTER":  # if this is a filter line
                # TODO: do filter staff
                pass
            elif line[0] == "}":
                STATE['IN_WHERE'] = False
            else:
                readPattern(line)

        else:
            print("Unexpected error while parsing line with tokens:", line)
            sys.exit()

    result = buildQuery()
    return result


def readPattern(pattern):
    """
    read a (subj pred obej) pattern, store the variable and sub-sql-query in the dictionary
    :param pattern: a list as [subj, pred, obej] pattern
    """
    QUERY_TEMPLATE = {(0,): ("subject as %s", "predicate = %s and object = %s"),
                      (1,): ("predicate as %s", "subject = %s and object = %s"),
                      (2,): ("object as %s", "subject = %s and predicate = %s"),
                      (0, 1): ("subject as %s, predicate as %s", "object = %s"),
                      (0, 2): ("subject as %s, object as %s", "predicate = %s"),
                      (1, 2): ("predicate as %s, object as %s", "subject = %s")}

    if pattern[2][-1] == ".":
        pattern[2] = pattern[2][:-1]

    variables = []
    conditions = []
    template_number = []
    print(pattern)
    for i in range(3):
        if pattern[i][0] == "?":  # if the term is a variable
            variables.append(pattern[i][1:])
            template_number.append(i)
        elif pattern[i][0] == "<":  # if the term is a url
            conditions.append(pattern[i][1:-1])
        elif ":" in pattern[i]:  # if it's a url with prefix
            index = pattern[i].index(":")
            if pattern[i][:index] not in PREFIX:
                print("Unknown prefix: ", pattern[i])
                sys.exit()
            url = PREFIX[pattern[i][:index]] + pattern[i][index + 1:]
            conditions.append(url)
        else:
            conditions.append(pattern[i])
        template_number = tuple(template_number)

    query = "SELECT DISTINCT %s FROM graph_data WHERE %s " \
            % (QUERY_TEMPLATE[template_number][0] % tuple(variables),
               QUERY_TEMPLATE[template_number][1] % tuple(conditions))

    SUB_VARS.append(variables)
    SUB_QUERIES.append(query)


def buildQuery():
    keys = SUB_VARS
    currentVars = set(keys.pop(0))
    # combine all the subqueries:
    query = SUB_QUERIES.pop(0)
    while any(keys):
        for i in range(len(keys)):
            vars = keys[i]
            if not currentVars.isdisjoint(set(vars)):
                commonVars = list(currentVars.intersection(set(vars)))
                if len(commonVars) > 1:
                    conditions = getConditionOn(commonVars)
                else:
                    conditions = "t1.%s = t2.%s" %(commonVars[0], commonVars[0])
                currentVars = currentVars.union(set(vars))
                query = "SELECT * FROM ((%s) as t1 JOIN (%s) as t2 on %s)" %(query, SUB_QUERIES.pop(i), conditions)
                keys.remove(vars)

    # TODO: add filter

    # output those needed:
    if OUTPUT_VAR != ["*"]:
        s = "%s "*len(OUTPUT_VAR)
        query = ("SELECT %s" % (s) )%tuple(OUTPUT_VAR) + "FROM ( " + query+ " );"

        # check error
        if not currentVars.issuperset(set(OUTPUT_VAR)):
            print("At least one of the output var is not in the where clause, out:",OUTPUT_VAR,"where:",currentVars)
            sys.exit()

    return query

def getConditionOn(vars):
    return ""

if __name__ == "__main__":
    main()
