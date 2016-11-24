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
FILTERS = []
FILTER_VAR = []


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
    # conn.create_function("convert",1,convert)
    # c.execute(query)
    # print(c.fetchall())

def convert(value):
    """
    this is a sql function that will try to convert value to int or float
    :param value: value of the object column that returned by a query
    :return: the converted value
    """
    try:
        if "." in value:
            a = float(value)
        else:
            a = int(value)

        return a
    except ValueError:
        return value

def reformat(string):
    """
    change the format of file so that:
      1. "SELECT" and "WHERE" will be in different lines
      2. (subj pred obj) and "WHERE {" will be in different lines
      3. there will be at least one space between SELECT and first ?var or *
      4. there will be at least one space between WHERE and {
      5. there will be at least one space between FILTER and (
    :param string: all the characters in the input file
    :return: a list of each line in the formatted file
    """
    # TODO: will the select and ?var in different lines?

    # changes #3
    select_index = string.upper().index("\nSELECT") + 6
    string = string[:select_index + 1] + " " + string[select_index + 1:]

    # changes #1,#2,#4
    where_index = 0
    while where_index < select_index:
        where_index = string.upper().find("WHERE", where_index + 1) + 4
    curly_open = string.find("{", where_index)
    string = string[:where_index - 4] + "\nWHERE {" + string[curly_open + 1:]

    # changes #5
    filter_index = string.upper().find("FILTER", 0)
    while filter_index >= 0:
        string = string[1:filter_index+6]+ " " +string[filter_index+6:]
        filter_index = string.upper().find("FILTER", filter_index)

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
                addFilter(line[1:])
            elif line[0] == "}":
                STATE['IN_WHERE'] = False
            else:
                readPattern(line)

        else:
            print("Unexpected error while parsing line with tokens:", line)
            sys.exit()

    result = buildQuery()
    return result

def addFilter(tokens):
    """
    add the filter line to the global variable
    :param tokens: all the token in the filter line
    """
    filterLine = "".join(tokens)
    variableStart = filterLine.find("?")
    varName = ""
    variableEnd = variableStart
    for char in filterLine[variableStart+1:]:
        if char not in ",><=)":
            varName += char
            variableEnd += 1
        else:
            break
    FILTER_VAR.append(varName)
    if "regx" in filterLine:
        first_quote = filterLine.find('''"''')
        if first_quote > 0:
            second_quote = filterLine.find('''"''',first_quote)
        else:
            first_quote = filterLine.find("'")
            second_quote = filterLine.find("'",first_quote)
        targetString = filterLine[first_quote+1:second_quote]
        FILTERS.append('''%s = "%s"''' % (varName,targetString) )
    else:
        # it has to be a number
        filterLine = filterLine[:variableStart+1] + filterLine[variableEnd+1:]
        number = ""
        operation = ""
        for char in filterLine:
            if char.isnumeric() or char == ".":
                number+=char
            else:
                break
        operations = ["!=", "=", ">=", "<=", ">","<"]
        for op in operations:
            if op in filterLine:
                operation = op
                break
        filterLine.find("!")
        FILTERS.append('''%s %s "%s"''' % (varName,operation,number))




def readPattern(pattern):
    """
    read a (subj pred obej) pattern, store the variable and sub-sql-query in the dictionary
    :param pattern: a list as [subj, pred, obej] pattern
    """

    QUERY_TEMPLATE = {(0,): ("subject as %s", '''predicate = "%s" and object = "%s"''', "predicate_object_index"),
                      (1,): ("predicate as %s", '''subject = "%s" and object = "%s"''', "subject_object_index"),
                      (2,): ("convert(object) as %s", '''subject = "%s" and predicate = "%s"''', "subject_predicate_index"),
                      (0, 1): ("subject as %s, predicate as %s", '''object = "%s"''', "object_index"),
                      (0, 2): ("subject as %s, convert(object) as %s", '''predicate = "%s"''', "predicate_index"),
                      (1, 2): ("predicate as %s, convert(object) as %s", '''subject = "%s"''', "subject_index")}

    if pattern[2][-1] == ".":
        pattern[2] = pattern[2][:-1]

    variables = []
    conditions = []
    template_number = []

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

    query = "SELECT DISTINCT %s FROM graph_data INDEXED BY %s WHERE %s " \
            % (QUERY_TEMPLATE[template_number][0] % tuple(variables),
               QUERY_TEMPLATE[template_number][2],
               QUERY_TEMPLATE[template_number][1] % tuple(conditions))

    SUB_VARS.append(variables)
    SUB_QUERIES.append(query)


def buildQuery():
    """
    use the global variables to construct a final query
    :return: the final sql query
    """
    keys = SUB_VARS
    currentVars = set(keys.pop(0))
    # combine all the subqueries:
    query = SUB_QUERIES.pop(0)
    while any(keys):
        for i in range(len(keys)):
            vars = keys[i]
            if not currentVars.isdisjoint(set(vars)):
                commonVars = tuple(currentVars.intersection(set(vars)))
                currentVars = currentVars.union(set(vars))
                query = "SELECT * FROM ((%s) as t1 JOIN (%s) as t2 USING " %(query, SUB_QUERIES.pop(i))
                query += "%s,"*(len(commonVars)-1)
                query += "%s)" % commonVars
                keys.remove(vars)

    # output those needed:
    if OUTPUT_VAR != ["*"]:
        s = "%s "*len(OUTPUT_VAR)
        query = ("SELECT %s" % (s) )%tuple(OUTPUT_VAR) + "FROM ( " + query+ " )"

        # check error
        if not currentVars.issuperset(set(OUTPUT_VAR)):
            print("At least one of the output var is not in the where clause, out:",OUTPUT_VAR,"where:",currentVars)
            sys.exit()

    if len(FILTERS) != 0:
        query += " where "
        for i in range(len(FILTERS)):
            if i == 0:
                query += FILTERS[i]
            else:
                query += " and " + FILTERS[i]

    query += ";"
    return query


if __name__ == "__main__":
    main()
