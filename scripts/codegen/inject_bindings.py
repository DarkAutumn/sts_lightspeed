import re

with open('include/constants/Potions.h', 'r') as f:
    potions_h = f.read()

# Extract potion names
match = re.search(r'enum class Potion : std::uint8_t \{(.*?)\};', potions_h, re.DOTALL)
if match:
    enum_content = match.group(1)
    
    # Clean up the enum content
    lines = enum_content.split('\n')
    potion_names = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('//'): continue
        
        # Remove comments at the end of the line
        line = line.split('//')[0].strip()
        
        # Extract the enum name
        parts = line.split('=')
        name = parts[0].strip().strip(',')
        if name:
            potion_names.append(name)

# Generate pybind code
pybind_code = '    pybind11::enum_<Potion>(m, "Potion")\n'
for name in potion_names:
    pybind_code += f'        .value("{name}", Potion::{name})\n'
pybind_code += '        ;\n'

with open('bindings/slaythespire.cpp', 'r') as f:
    cpp_code = f.read()

# Insert enum binding
enum_insertion_point = '    pybind11::enum_<GameOutcome>(m, "GameOutcome");'
cpp_code = cpp_code.replace(enum_insertion_point, pybind_code + '\n' + enum_insertion_point)

# Insert GameContext properties
game_context_props = """
        .def_property_readonly("potion_count", [](const GameContext &gc) { return gc.potionCount; })
        .def_property_readonly("potions",
            [](const GameContext &gc) {
                return std::vector<Potion>(gc.potions.begin(), gc.potions.begin() + gc.potionCapacity);
            },
            "returns a copy of the list of potions currently held"
        )"""

gc_insertion_point = """        .def_property_readonly("relics",
               [] (const GameContext &gc) { return std::vector(gc.relics.relics); },
               "returns a copy of the list of relics"
        )"""

cpp_code = cpp_code.replace(gc_insertion_point, gc_insertion_point + game_context_props)

# Insert get_potion_name function
func_insertion_point = '    m.def("get_seed_long", &SeedHelper::getLong, "gets the seed string representation of an integral seed");'
func_code = '\n    m.def("get_potion_name", &sts::getPotionName, "Get the string name of a potion");'

cpp_code = cpp_code.replace(func_insertion_point, func_insertion_point + func_code)

with open('bindings/slaythespire.cpp', 'w') as f:
    f.write(cpp_code)

print("Injected Python bindings.")
