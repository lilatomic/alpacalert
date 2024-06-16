import subprocess
import os


def shell(cmd: str):
	subprocess.run(cmd, shell=True, check=True)

def k8sfile(path: str):
	shell(f"kubectl apply -f {filepath(path)}")

def filepath(relative_path: str) -> str:
	return os.path.join("src/it/resources/", relative_path)

k8sfile("names.yml")

def prom():
	shell("helm repo add prometheus-community https://prometheus-community.github.io/helm-charts")
	shell("helm repo update")

	shell(f"helm upgrade --install --namespace prom prom prometheus-community/kube-prometheus-stack -f {filepath('prometheus.yml')}")

prom()

def nginx():
	shell("kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml --namespace ingress-nginx")
	k8sfile("ingress_test.yml")

nginx()

k8sfile("k8s_objects.yml")
