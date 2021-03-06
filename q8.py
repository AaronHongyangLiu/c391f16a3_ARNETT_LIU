import sqlite3  # https://docs.python.org/2/library/sqlite3.html
import sys
import re

PREFIX_URL = {}
DB_DATA = []  # this holds the tuples that will be inserted in DB

STATE = {
    'SAME_SUBJECT': False,
    'SAME_PREDICATE': False,
    'SAME_OBJECT': False
}

END_LINE_TOKENS = ['.', ',', ';']
BASE_URL = None


def main():
    if len(sys.argv) != 3:
        print "Usage: python q8.py <database file> <RDF input file>"
        sys.exit()

    db = sqlite3.connect(sys.argv[1])
    db.text_factory = str
    infile = open(sys.argv[2], 'r')  # read the RDF data file
    input_lines = infile.readlines()
    infile.close()

    parse_file(input_lines)

    insert_data(db)
    db.close()


def parse_file(lines):
    """
    parses lines of the file for insertion to the database
    param lines: the list of lines read from RDF data file
    """

    # Initialization
    subject = None
    predicate = None
    object = None
    obj_type = None

    for line in lines:
        line = line.replace('\t', ' ').strip()  # replace tabs with spaces

        if '#' in line and "<" not in line and ">" not in line:  # Then comment exists and we ignore
            # we check for presence of "<" and ">" because '#'s can be found in urls and urls are encased in '<' and '>'
            index = line.find('#')
            line = line[:index].rstrip()
            line += '\n'  # add newline character to keep format consistent

        if line.strip() == "":  # Ignore blank lines
            continue

        if line.strip('\n')[-1] not in END_LINE_TOKENS:
            print "There is a line missing a valid end-line token. '%s' not in %s" % (
                line.strip('\n')[-1], END_LINE_TOKENS)
            sys.exit(1)

        if iri_exists(line):
            continue

        line_contents = line.split()
        line_contents = join_literal(line_contents)

        # generate new triple without any existing context
        if len(line_contents) == 4 and not STATE['SAME_SUBJECT'] and not STATE['SAME_PREDICATE']:
            subject, predicate, object, obj_type = get_attributes(line_contents, predicate=None,
                                                                                    subject=None)

        # generate triple with existing subject and predicate
        elif len(line_contents) == 2 and STATE['SAME_SUBJECT'] and STATE['SAME_PREDICATE']:
            subject, predicate, object, obj_type = get_attributes(line_contents, predicate=predicate,
                                                                  subject=subject)

        # generate triple with existing subject but new predicate
        elif len(line_contents) == 3 and STATE['SAME_SUBJECT'] and not STATE['SAME_PREDICATE']:
            subject, predicate, object, obj_type = get_attributes(line_contents, predicate=None,
                                                                  subject=subject)
        else:
            print "Syntax error - Invalid use of end-line token (expected a different end line token than the one given)."
            sys.exit(1)

        object = is_english(object)  # returns english object, or None if not english
        if object:
            DB_DATA.append((subject, predicate, object, obj_type))

    return


def iri_exists(line):
    """
    This function checks a line to see if it contain an IRI. If there is an IRI then it will assign
    it to the global variable.
    :param line: The line to check for IRI
    :return: False if no IRI, True if contains IRI
    """
    # check if prefix declaration line
    prefix_rdf = re.search("(?:^)@prefix(.*)", line)  # https://docs.python.org/2/howto/regex.html
    prefix_sparql = re.search("(?:^)PREFIX(.*)", line)
    base_rdf = re.search("(?:^)@base(.*)", line)
    base_sparql = re.search("(?:^)BASE(.*)", line)

    prefix_types = [prefix_rdf, prefix_sparql]
    base_types = [base_rdf, base_sparql]

    prefix = None
    base = None
    if any(prefix_types):
        for r in prefix_types:
            if r:
                prefix = r
        if not STATE['SAME_PREDICATE'] and not STATE['SAME_SUBJECT']:  # Checks if previous line has '.' endline token
            add_prefix(prefix)
            return True
        else:
            print "Syntax error - Invalid use of end-line token (expected a different end line token than the one given)."
            sys.exit(1)

    elif any(base_types):
        for b in base_types:
            if b:
                base = b

        if not STATE['SAME_PREDICATE'] and not STATE['SAME_SUBJECT']:  # Checks if previous line has '.' endline token
            add_base(base)
            return True
        else:
            print "Syntax error - Invalid use of end-line token (expected a different end line token than the one given)."
            sys.exit(1)
    else:
        return False  # Doesn't contains any IRI's in line


def join_literal(line_contents):
    """
    There are likely spaces in the literals given in RDF data, but since we split the lines by spaces
    the literal will be broken up. This method joins the literal back together.
    :param line_contents: the space separated line in array form
    :return: the line contents with literals joined at the spaces
    """
    start_index = None
    end_index = None
    for i in range(len(line_contents)):
        if '"' in line_contents[i] and line_contents[i].count('"') == 1:
            if start_index == None and end_index == None:
                start_index = i
            elif start_index != None and end_index == None:
                end_index = i

    if start_index == None and end_index == None:
        return line_contents

    obj = ''
    for j in range(start_index, end_index + 1):
        obj += '%s ' % line_contents[j]

    array_result = []
    for k in range(len(line_contents)):
        if k < start_index:
            array_result.append(line_contents[k])
        elif k == start_index:
            array_result.append(obj.strip())
        elif start_index < k <= end_index:
            continue
        else:
            array_result.append(line_contents[k])

    return array_result


def get_attributes(line_contents, predicate, subject):
    """
    based on the line being parsed, the appropriate DB ready attributes are generated
    :param line_contents: The array of the tab separated line
    :param predicate: The current predicate resource that applies to the line being parsed. AKA the context of the line
    :param subject: The current subject resource that applies to the line being parsed. AKA the context of the line
    :return: the attributes ready to be inserted into DB
    """
    object = None  # initialization
    global STATE

    if not subject and not STATE['SAME_SUBJECT']:  # Then new subject being encountered
        subject = get_url_syntax(line_contents[0])
        if not subject:  # Then in prefix form
            subject = translate_tag(line_contents[0])
        STATE['SAME_SUBJECT'] = True

        predicate = get_url_syntax(line_contents[1])
        if not predicate:
            predicate = translate_tag(line_contents[1])

    if subject and not predicate and STATE['SAME_SUBJECT'] and not STATE['SAME_PREDICATE']:
        predicate = get_url_syntax(line_contents[0])
        if not predicate:
            predicate = translate_tag(line_contents[0])

    end_line_token = line_contents[-1]

    object = get_url_syntax(line_contents[-2])

    if end_line_token == ',':  # new object under same predicate and subject
        if not object:  # Then object is in prefix form
            object_with_prefix = line_contents[-2]

        STATE['SAME_SUBJECT'] = True
        STATE['SAME_PREDICATE'] = True

    elif end_line_token == '.':
        if not object:
            object_with_prefix = line_contents[-2]

        STATE['SAME_SUBJECT'] = False
        STATE['SAME_PREDICATE'] = False

    elif end_line_token == ';':  # new predicate
        if not object:
            object_with_prefix = line_contents[-2]

        STATE['SAME_SUBJECT'] = True
        STATE['SAME_PREDICATE'] = False

    else:
        print ("invalid or missing identifier at end of line")
        sys.exit(1)

    # handle prefix tags with other data
    if not object:
        if ":" in object_with_prefix and "^^" not in object_with_prefix:
            object = translate_tag(object_with_prefix)

        else:  # Then we do not have a url
            object = object_with_prefix

    object, obj_type = determine_type(object)

    return subject, predicate, object, obj_type


def determine_type(object):
    """
    determines the object's type. If the object contains a prefix then the obj_type will be a url describing object type
    and the object will be the string before the tag was included.
    example:
        if input is "812201"^^xsd:nonNegativeInteger
        then result will be:
            object = "812201"
            object_type = http://www.w3.org/2001/XMLSchema#nonNegativeInteger
    :param object: the object whose type is to be determined
    :return: object in string representation, a tag of it's type
    """
    object_type = 'other'  # 'other' by default

    try:
        if "." in object:
            numerical_object = float(object)
            object_type = 'float'
        else:
            numerical_object = int(object)
            object_type = 'int'

    except ValueError:
        if "http://" in object:
            object_type = 'url'
        else:
            object_type = "literal"

        if "^^" in object:
            object_contents = object.split("^^")
            object = object_contents[0]
            object_type = translate_tag(object_contents[1])

    return object, object_type


def get_url_syntax(object):
    """
    determines if object is given in URI form or url form. If in url or IRI form it returns the url,
    otherwise returns None
    :return: objects url if input is url form, otherwise None
    """
    if "<" in object and ">" in object:
        object = object[object.find("<") + 1:object.find(">")]
        if "http://" not in object:
            object = "%s%s" % (BASE_URL, object)

        return object
    return None


def translate_tag(tag):
    """
    generates the text that will be saved in database
    WARNING - blank nodes are stored as they come. _:b27527865 ---> _:b27527865
    :param tag: example -->  dbr:Edmonton
    :return: the tag without prefixes ---> 'http://dbpedia.org/resource/Edmonton'
    """
    if ":" not in tag:
        print "Invalid character found in input. Line contents = '%s'" % tag.strip('\n')
        sys.exit(1)
    tag_contents = tag.split(':')
    if tag_contents[0] == "_":
        return tag.strip()

    if tag_contents[0] not in PREFIX_URL.keys():
        print "prefix tag '%s' is undefined in input file." % tag_contents[0]
        sys.exit(1)

    result = "%s%s" % (PREFIX_URL[tag_contents[0]], tag_contents[1])
    return result


def add_base(base):
    """
    given a string with a base IRI (ex. <http://one.example/> this function
    will add the IRI to the global BASE_URL variable.
    """
    global BASE_URL
    base_contents = base.group(1).strip().split()

    if len(base_contents) != 2:
        print "Invalid base IRI tag in input file"
        sys.exit(1)
    if base_contents[1] != '.':
        print "Prefix line must end with a '.' not '%s'" % base_contents[1]
        sys.exit(1)

    # this gets the url of the prefix tag. http://stackoverflow.com/questions/4894069/regular-expression-to-return-text-between-parenthesis
    url = base_contents[0][base_contents[0].find("<") + 1:base_contents[0].find(
        ">")]

    BASE_URL = url
    return

def add_prefix(prefix):
    """
    given a string with a prefix (ex. rdf:	<http://www.w3.org/1999/02/22-rdf-syntax-ns#> this function
    will add the key/value pair (key = rdf, value = http://www.w3.org/1999/02/22-rdf-syntax-ns#) to the PREFIX_URL
    dictionary
    """
    prefix_contents = prefix.group(1).strip().split()

    if len(prefix_contents) != 3:
        print "Invalid prefix tag in input file"
        sys.exit(1)
    if prefix_contents[2] != '.':
        print "Prefix line must end with a '.' not '%s'" % prefix_contents[2]
        sys.exit(1)

    # this gets the url of the prefix tag. http://stackoverflow.com/questions/4894069/regular-expression-to-return-text-between-parenthesis
    url = prefix_contents[1][prefix_contents[1].find("<") + 1:prefix_contents[1].find(
        ">")]

    PREFIX_URL[prefix_contents[0].strip()[:-1]] = url  # Add to the PREFIX_URL dictionary


def insert_data(db):
    """
    function that inserts the data to DB in a bulk insert.

    from: https://docs.python.org/2/library/sqlite3.html
    :param db: database instance
    """

    cursor = db.cursor()
    if cursor:
        # for triple in DB_DATA:
        #     print triple
        # print len(DB_DATA)
        cursor.executemany('INSERT INTO graph_data VALUES (?,?,?,?)', DB_DATA)
        db.commit()
    else:
        print 'Something went wrong while creating the DB cursor!'
        sys.exit(1)

    return


def is_english(object):
    """
    determines if the input attributes are english or not and removes language tag if found
    :param object: the term to check for english qualities
    :return: object ready for
    """
    language_tag = re.search("@[a-z]*", object)
    if language_tag:
        if language_tag.group() != "@en":
            return None  # Was another language
        else:
            object = object.replace("@en", '')
    return object


if __name__ == "__main__":
    main()
