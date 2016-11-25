def main():
    infile = open("Edmonton.txt", 'r')
    wholefile = infile.read()
    lines = wholefile.split("\n")

    # newLines is all the lines with all the objects in the same line
    newLines = []
    NeedCombine = False
    temp = ""
    lineNumber = []
    number = 0
    for line in lines:
        line = line.strip()
        if NeedCombine:
            line = temp + line
            if line[-1] in [".", ";"]:
                NeedCombine = False
                newLines.append(line)
                lineNumber.append(number)
                number += 1
            elif line[-1] == ",":
                temp = line
            else:
                print("something wrong, line=", line)
                exit()
        else:
            if line[-1] == ",":
                temp = line
                NeedCombine = True
            else:
                newLines.append(line)
                number += 1

    for j in range(len(newLines)):
        tokens = newLines[j].split('"')
        for i in range(len(tokens)):
            if i % 2 == 0:
                nonLiteralTerm = tokens[i]
                nonLiteralTerm = nonLiteralTerm.split()
                tokens[i] = " ".join(nonLiteralTerm)
            else:
                #   tokens[i - 1] = tokens[i - 1] + " "
                if i == 1:
                    tokens[i - 1] = tokens[i - 1] + " "
        newLines[j] = '"'.join(tokens)

    # to undo making all the object in the same line
    for k in range(len(newLines)):
        if k in lineNumber:
            # print("line : ", newLines[k])
            tokens = newLines[k].split(",")
            for s in range(len(tokens)):
                if s != (len(tokens) - 1):
                    tokens[s + 1] = "\n" + tokens[s + 1]
            newLines[k] = ",".join(tokens)

    newfile = "\n".join(newLines)
    print(newfile)


main()
