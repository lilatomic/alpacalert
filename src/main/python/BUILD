resource(name="pyproject", source="pyproject.toml")

python_requirements(source="pyproject.toml")

relocated_files(
	name="README.md",
	files_targets=["//:README.md"],
	src="",
	dest="src/main/python/",
)

python_distribution(
	name="alpacalert",
	dependencies=[
		":pyproject",
		":README.md",
		"./alpacalert:src",
		"./alpacalert/instrumentors:instrumentors",
		"./alpacalert/visualisers:visualisers",
	],
	provides=python_artifact(
		name="alpacalert",
		version="0.1.1",
	),
	generate_setup=False,
)
