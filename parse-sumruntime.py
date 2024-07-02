
data = """
72264 15530
72264 2
72264 3
72264 14029
72266 20704
72273 7937
72273 12725
72268 19616
72263 17414
72265 16296
72270 16349
72272 18928
72271 16382
72271 17
72271 4130
72274 17814
72274 3425
72269 21250
72275 12532
72275 7918
72265 18168
72263 7721
72263 25
72263 13278
72270 16494
72268 18017
72266 17333
72273 16820
72272 16621
72271 12787
72271 8117
72264 18606
72274 17023
72275 9990
72275 6
72275 10091
72269 19312
72267 19432
72265 12168
72265 14146
72277 19197
72277 2751
72273 17354
72268 7095
72268 14698
72276 19085
"""
# Split the data into lines and then into pairs of values
lines = [line.split() for line in data.strip().split('\n')]
numbers = [(int(line[0]), int(line[1])) for line in lines]

# Create a dictionary to sum the values
sum_dict = {}
for key, value in numbers:
    if key in sum_dict:
        sum_dict[key] += value
    else:
        sum_dict[key] = value

# Print the results
for key, value in sum_dict.items():
    print(key, value)
