resource(name="pyproject", source="pyproject.toml")

python_requirements(source="requirements.txt")

python_distribution(
	name="alpacalert_cmd",
	dependencies=[
		":pyproject",
		"./alpacalert_cmd:src",
	],
	provides=python_artifact(
		name="alpacalert_cmd",
		version="0.1.0",
	),
	generate_setup=False,
)
