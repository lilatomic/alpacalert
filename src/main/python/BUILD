resource(name="pyproject", source="pyproject.toml")

python_requirements(source="pyproject.toml")

python_distribution(
	name="alpacalert",
	dependencies=[
		":pyproject",
		"./alpacalert:src",
		"./alpacalert/instrumentors:instrumentors",
		"./alpacalert/visualisers:visualisers",
	],
	provides=python_artifact(
		name="alpacalert",
		version="0.1.0",
	),
	generate_setup=False,
)
