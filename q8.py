import sqlite3  # https://docs.python.org/2/library/sqlite3.html
import sys
import re

PREFIX_URL = {}

STATE = {
    'IN_SUBJECT' : False,
    'IN_PREDICATE' : False,
    'IN_OBJECT' : False
}



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
    subject = None
    predicate = None
    object = None

    for line in lines:
        # check if prefix line
        prefix = re.search("(?:)@prefix(.*)", line)  # https://docs.python.org/2/howto/regex.html
        if prefix:
            add_prefix(prefix)
            continue # go to next line
        line_contents = line.split('\t')




        # if not STATE['IN_SUBJECT']: # Then new triple
        if line_contents[0] != '':  # then subject field available
            subject = generate_attribute(line_contents[0])
            STATE['IN_SUBJECT'] = True
            predicate = generate_attribute(line_contents[1])

            if line_contents[2][-2] == ',':
                object_with_prefix = re.search("^[^,]*",line_contents[2]).group() # regex from http://stackoverflow.com/questions/19142042/python-regex-to-get-everything-until-the-first-dot-in-a-string
                object = generate_attribute(object_with_prefix)
                insert_triple(db, subject, predicate, object)
            if line_contents[2][-2] == '.': # -2 index because last character is newline character
                object_with_prefix = re.search("^[^.]*", line_contents[
                    2]).group()  # regex from http://stackoverflow.com/questions/19142042/python-regex-to-get-everything-until-the-first-dot-in-a-string
                object = generate_attribute(object_with_prefix)
                insert_triple(db, subject, predicate, object)
                subject = None
                predicate = None
                object = None
        elif line_contents[0] == '' and line_contents[1] == '' and subject and predicate:
            object_with_prefix = re.search("^[^,]*", line_contents[
                2]).group()  # regex from http://stackoverflow.com/questions/19142042/python-regex-to-get-everything-until-the-first-dot-in-a-string
            object = generate_attribute(object_with_prefix)
            insert_triple(db, subject, predicate, object)



        # if STATE['IN_SUBJECT']:
        #     print line_contents




def generate_attribute(tag):
    """
    generates the text that will be saved in database
    :param tag: example -->  dbr:Edmonton
    :return: the tag without prefixes
    """
    tag_contents = tag.split(':')
    print tag
    result = "%s%s" % (PREFIX_URL[tag_contents[0]], tag_contents[1])
    return result

def add_prefix(prefix):
    prefix_contents = prefix.group(1).split('\t')

    # this gets the url of the prefix tag. http://stackoverflow.com/questions/4894069/regular-expression-to-return-text-between-parenthesis
    url = prefix_contents[1][prefix_contents[1].find("<") + 1:prefix_contents[1].find(
        ">")]

    PREFIX_URL[prefix_contents[0].strip()[:-1]] = url  # Add to the PREFIX_URL dictionary

def insert_triple(db, subject, predicate, object):
    print '\n'

    print subject
    print predicate
    print object
    print '\n'

    # TODO insert into the DB
    return

# def new_triple():
#     """
#     :return: true if not currently parsing a previous triple
#     """
#     return (not STATE['IN_OBJECT'] and not STATE['IN_PREDICATE'] and not STATE['IN_SUBJECT'])

if __name__ == "__main__":
    main()
