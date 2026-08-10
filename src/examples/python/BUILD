resource(name="pyproject", source="pyproject.toml")

python_requirements(source="requirements.txt")

python_distribution(
	name="alpacalert_cmd",
	dependencies=[
		":pyproject",
		":README.md",
		"./alpacalert_cmd:src",
	],
	provides=python_artifact(
		name="alpacalert_cmd",
		version="0.1.2",
	),
	generate_setup=False,
)

files(name="README.md", sources=["README.md"])
