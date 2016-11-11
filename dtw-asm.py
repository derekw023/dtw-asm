#!/usr/bin/env python3
import sys
import argparse
import re
import json

EXIT_STATUS = 0 # Flag to store current error state. anything non-zero is bad and will kill program at certain checkpoints

parser = argparse.ArgumentParser()
parser.add_argument("asm_file", help="Assembly directives to assemble")
parser.add_argument("-o", "--outfile", help="Output MIF format file for FPGA program", default="asm-out.mif")
parser.add_argument("--opcodes", help="JSON Definition file to map mnemonics to opcodes")
parser.add_argument("-v", "--verbose", action="store_true", help="Generate verbose output")
args = parser.parse_args()

if args.opcodes:
	with open(parser.opcodes, 'r') as infile: opcodes = json.read(parser.opcodes)
else:
	opcodes = {	"LD":	int("0b0000", 0),
				"ST":	int("0b0001", 0),
				"CPY":	int("0b0010", 0),
				"SWAP":	int("0b0011", 0),
				"ADD":	int("0b0100", 0),
				"SUB":	int("0b0101", 0),
				"ADDC":	int("0b0110", 0),
				"SUBC":	int("0b0111", 0),
				"AND":	int("0b1000", 0),
				"OR":	int("0b1001", 0),
				"NOT":	int("0b1010", 0),
				"SHRA":	int("0b1011", 0),
				"ROTR":	int("0b1100", 0),
				"ADDV":	int("0b1110", 0),
				"MSUB":	int("0b1111", 0),
				"JMP":	int("0b1101", 0),
				"JMPC":	int("0b1101", 0),
				"JMPN":	int("0b1101", 0),
				"JMPV":	int("0b1101", 0),
				"JMPZ":	int("0b1101", 0),
				"JMPNC":	int("0b1101", 0),
				"JMPNN":	int("0b1101", 0),
				"JMPNV":	int("0b1101", 0),
				"JMPNZ":	int("0b1101", 0)}



JMP_conditions = {	"JMP":		int("0b00000", 0),
					"JMPC":	int("0b10000", 0),
					"JMPN":	int("0b01000", 0),
					"JMPV":	int("0b00100", 0),
					"JMPZ":	int("0b00010", 0),
					"JMPNC":	int("0b01110", 0),
					"JMPNN":	int("0b10110", 0),
					"JMPNV":	int("0b11010", 0),
					"JMPNZ":	int("0b11100", 0)}
##### Constant array with ASCII test data, specifically for use in Lab10
##### accessed by initializing a .array with content "Lab10"
Lab10_array = []
for i in range(0, 64):
	Lab10_array.append((ord("D") << 7) + ord("E"))
	Lab10_array.append((ord("a") << 7) + ord("d"))
	Lab10_array.append((ord("4") << 7) + ord("2"))
	Lab10_array.append((ord(",") << 7) + ord(" "))

# Functions are provided for reusability
def parse_register(register):
	if not re.search(r'^[r|R]', register): 
		print("Error: {0} instructions require a valid register as the first argument, denoted by R or r!!!!!\nExpected R\d, got {1}".format(instruction['mnemonic'], register))
		sys.exit(2)
	register = int(re.sub(r'^[R|r]', '', register), 0) # Convert to register number
	if register > 31: 
		print("Error: This processor only has 32 registers, {0} is invalid for this architecture".format(register))
		sys.exit(2)
	return  register	

##### Read in file and do first syntax pass, strip whitespace and lines that are comments as well as empty lines
##### Also process each line into list of sylables
##### Then push that line into a list of statements, the list is selected by the "statement" variable, controlled by section headers
parsed_input = []
asm = {}
asm['directives'] = []
asm['constants'] = []
asm['code']	= []
with open(args.asm_file, 'r') as infile:
	for i, line in enumerate(infile):
		raw_line = line # save unmodified line
		line = line.strip() 
		if len(line) == 0: continue # Skip empty lines
		if line[0] == ";": continue	# Skip lines that only contain comments
		if not re.search(r';.*$', line): print('Warning: Line {0} missing semicolon')
		line = re.sub(r';.*$', '', line) # Strip out comments using semicolon as comment character
		line = re.split(r'[\s,]+', line.strip())
		# line contains parsed assembly code, interpret section headers and divide statements into their respective sections
		if line[0] in [".directives", ".constants", ".code"]: 
			section = re.sub(r'\.', '', line[0])
			continue
		if line[0] in [".enddirectives", ".endconstants", ".endcode"]: 
			section = ""
			continue
		if len(section) > 0: 
			asm[section].append({'list':line, 'raw': raw_line})
			continue
		print("Warning: Code line {0} not in a section, will have no influence on machine code".format(i))

if args.verbose:
	print("Assembly code is as follows:")
	print("Code:")
	for line in asm['code']: print(line)
	print("Directives:")
	for line in asm['directives']: print(line)
	print("Constants:")
	for line in asm['constants']: print(line)

##### Deal with directives (like #defines)
##### -Here we also define some static directives that are always there, like aliases
global_directives={
		"COPY":		"CPY",
		"LOAD":		"LD",
		"STORE":	"ST",
		"JC":		"JMPC",
		"JN":		"JMPN",
		"JV":		"JMPV",
		"JZ":		"JMPZ",
		"JNC":		"JMPNC",
		"JNN":		"JMPNN",
		"JNV":		"JMPNV",
		"JNZ":		"JMPNZ"}
for directive in asm['directives']:
	if directive['list'][0] == ".equ": global_directives[directive['list'][1]] = directive['list'][2]
	else: 
		print("Error: Directive {0} not recognized!") # If directive not recognized, error out and set exit flag
		EXIT_STATUS = 2

##### Deal with constants
global_constants = {}
for constant in asm['constants']:
	if constant['list'][0] == ".word": global_constants[constant['list'][1]] = constant['list'][2]
	elif constant['list'][0] == ".array":
		if constant['list'][2] == "Lab10":
			global_constants[constant['list'][1]] = Lab10_array # predefined, see code above 
		else:
			global_constants[constant['list'][1]] = constant['list'][2:] 
	else: 
		print("Error: Constant {0} not recognized!".format(constant['list'])) # If constant not recognized, error out and set exit flag
		EXIT_STATUS = 2

##### Substitute directives in code section
for i, line in enumerate(asm['code']):
	for j, arg in enumerate(line['list']):
		for name in global_directives: line['list'][j] = re.sub(name, global_directives[name], line['list'][j])
	asm['code'][i] = line

##### Begin to assemble code, insert placeholders for labels and constants, need to sweep through again and replace them all
ram_prep = [] # list to hold data on what will be going into ram, indexed by instruction
for line_number, line in enumerate(asm['code']):
	instruction = {}
	if line['list'][0][0] == '@': instruction['label'] = line['list'].pop(0)[1:]
	instruction['mnemonic'] = line['list'].pop(0).upper()

	# All of these instructions use a register as the first operand, parse the register number and push it onto the instruction dict
	if instruction['mnemonic'] in ['ADDV', 'ADD', 'ADDC', 'SUB', 'SUBC', 'AND', 'OR', 'NOT', 'SHRA', 'ROTR', 'LD', 'ST', 'CPY', 'SWAP']: 
		instruction['Ri'] = parse_register(line['list'].pop(0))
	
	# Parse and interpret the second operand for register-register instructions
	if instruction['mnemonic'] in ['ADDV', 'ADD', 'SUB', 'AND', 'OR', 'CPY', 'SWAP']: 
		instruction['Rj'] = parse_register(line['list'].pop(0))
	
	# For Add constant and Sub constant, take the constant and put it in Rj
	# Also ROTR and SHRA use a number specified in asm file like ADDC and SUBC
	if instruction['mnemonic'] in ['ADDC', 'SUBC', 'SHRA', 'ROTR']:
		instruction['Rj'] = int(line['list'].pop(0), 0)

	# for NOT, we don't use Rj. set it to 0
	if instruction['mnemonic'] in ['NOT']:
		instruction['Rj'] = 0
	
	# Load and Store are register-memory, implement RAM addressing modes here. Also parse the address and determine
	# -the appropriate IW1 and Rj to point to the right RAM location
	# Also need to implement labeling to point to constants and initialized variables from directives section
	if instruction['mnemonic'] in ['LD', 'ST']:
		address = line['list'].pop(0)
		# Determine general form: register indexed or immediate - indexed form is 0xBeEF[Rj] or @LABEL[Rj]
		if re.search(r'\[[R|r].*\]', address):
			instruction['Rj'] = parse_register(re.search(r'\[[R|r].*\]', address).group(0).strip('\[\]'))
			address = re.sub(r'\[[R|r].*\]', '', address)
		else: instruction['Rj'] = 0

		# If a label is included in the line, flag that we need it replaced. IW1 empty.
		if address[0] is '@':
			instruction['address_label'] = address[1:]
			instruction['IW1'] = "" # IW1 exists, but is zero-length. needs to be filled later
		else: instruction['IW1'] = int(address, 0)
	if instruction['mnemonic'][0:3]  in JMP_conditions:
		instruction['Rj'] = JMP_conditions[instruction['mnemonic']]
		address = line['list'].pop(0)
		if re.search(r'\[[R|r].*\]', address):
			instruction['Ri'] = parse_register(re.search(r'\[[R|r].*\]', address).group(0).strip('\[\]'))
			address = re.sub(r'\[[R|r].*\]', '', address)
		else: instruction['Ri'] = 0

		# If a label is included in the line, flag that we need it replaced. IW1 empty.
		if address[0] is '@':
			instruction['address_label'] = address[1:]
			instruction['IW1'] = "" # IW1 exists, but is zero-length. needs to be filled later
		else: instruction['IW1'] = int(address, 0)
		
	# IF WE ARE HERE AND ANYTHING IS LEFT IN THE INSTRUCTION THAT IS AN ERROR!!!!!!
	# ALL TEXT IN CODE SECTION MINUS COMMENTS SHOULD BE USED IN THE ASSEMBLY STEP!
	if len(line['list']) is not 0: 
		for text in line['list']: print('Warning: The text "{0}"  has no effect on the compiled program!'.format(text))
		EXIT_STATUS=1
	if len(line['raw']) > 0:instruction['comment'] = line['raw']
	else: instruction['comment']= ''
	ram_prep.append(instruction)
if EXIT_STATUS > 1: sys.exit(EXIT_STATUS)

global_labels = {}
# Sweep through ram_prep and find or replace labels
instruction_address = 0 # counter/pointer to keep track of where we are in the program memory map
for instruction in ram_prep:
	if ('label' in instruction and instruction['label'] in global_labels):
		print("Error: Label {0} cannot be defined more than once".format(instruction['label']))
		EXIT_STATUS = 2
	elif 'label' in instruction: 
		global_labels[instruction['label']] = instruction_address
		if args.verbose: print("Found Label {0} at address 0x{1:X}".format(instruction['label'], instruction_address))
	if 'IW1' in instruction: instruction_address += 2
	else: instruction_address += 1
if EXIT_STATUS > 1: sys.exit(EXIT_STATUS)
# Allocate constants
for constant in global_constants:
	global_labels[constant] = instruction_address # make a label for constants, syntax like @constant_name
	if type(global_constants[constant]) is list: #Handle arrays
		for i, element in enumerate(global_constants[constant]):
			ram_prep.append({'mnemonic': 'CONST', 'IW0': int(element), 'comment': 'Array {}[{}]'.format(constant, i)})
			instruction_address += 1
	else: 
		ram_prep.append({'mnemonic': 'CONST', 'IW0': int(global_constants[constant], 0), 'comment': 'Constant: {}'.format(constant)})# setup the value of the constant
		instruction_address += 1

if args.verbose:
	for word in ram_prep: print(json.dumps(word, indent=True, sort_keys=True))
RAM_OUT = []
for instruction in ram_prep:
	if instruction['mnemonic'] in ['ADDC', 'SUBC', 'SHRA', 'ROTR', 'ADD', 'ADDV', 'SUB', 'AND', 'OR', 'NOT', 'CPY', 'SWAP']: # Do single word instructions(IE register-register instructions)
		if 'Ri' in instruction and 'Rj' in instruction and 'mnemonic' in instruction:
			IW0 = (opcodes[instruction['mnemonic']] << 10) + (instruction['Ri'] << 5) + instruction['Rj']
			RAM_OUT.append({'content': IW0, 'comment': instruction['comment']})
		else: raise SyntaxError("Something went seriously wrong, got to assembly stage without fully defined instructions")
	if (instruction['mnemonic'] in JMP_conditions) or (instruction['mnemonic'] in ['ST', 'LD']): # Do 2-word memory related instructions, also jumps
		IW0 = (opcodes[instruction['mnemonic']] << 10) + (instruction['Ri'] << 5) + instruction['Rj']
		RAM_OUT.append({'content': IW0, 'comment': instruction['comment']})
		if type(instruction['IW1']) is int: RAM_OUT.append({'content': instruction['IW1'], 'comment': ''})
		elif 'address_label' in instruction: RAM_OUT.append({'content': global_labels[instruction['address_label']], 
															 'comment': 'Label: {}'.format(instruction['address_label'])})
		else:
			print("Error: IW1 was empty, is label {0} defined?".format( instruction['address_label']))
			EXIT_STATUS = 2
	if instruction['mnemonic'] == 'CONST': RAM_OUT.append({'content': instruction['IW0'], 'comment': instruction['comment']})
if EXIT_STATUS > 1: sys.exit(EXIT_STATUS)

##### Generate and write out syntax for MIF, now that we have a memory map generated
with open(args.outfile, 'w') as outfile:
	outfile.write("-- Memory file\n--Source file: {0}\n--Assembled for DTWRISC521 ISA".format(args.asm_file))
	outfile.write('\n')
	outfile.write('WIDTH = 14;\n')
	outfile.write('DEPTH = 16000;\n')
	outfile.write('\n')
	outfile.write('ADDRESS_RADIX = HEX;\n')
	outfile.write('DATA_RADIX = HEX;\n')
	outfile.write('CONTENT BEGIN\n')
	address = 0;
	for word in RAM_OUT:
		outfile.write('{0:X}\t:\t{1:04X}; %{2}%\n'.format(address, word['content'], word['comment'].strip()))
		address += 1
	outfile.write('END;\n')

sys.exit(EXIT_STATUS)
	


# vim:nu
