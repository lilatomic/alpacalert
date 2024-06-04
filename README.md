# Alpacalert

Alpacalert is a monitoring tool which understands your infrastructure as interacting services. 

## Alpacalert Conceptual Overview

Alpacalert models your infrastructure using 3 primitives: Sensors, Systems, and Services.

- Sensors : These reach out to the world and measure something. That could be the status of a running process, available disk space, or availability of a healthcheck endpoint; for example.
- Systems : These compose Sensors and other Systems into logical units of infrastructure. Systems also make determinations about their health by using data from their Sensors. Some examples of systems:
    - a kubernetes service pointing to a statefulset which references secrets, configmaps, and PVCs; and which depends on its pods being scheduled on kubernetes nodes
    - a Virtual Machine with processors, RAM, and disk space. A virtual machine might have limits for the expected RAM or processor usage, or might warn when it is low on disk space.
    - a message queue. An application which uses a message queue might check that the system running the queue is reachable, that the provided credentials work, and that the expected queues exist.
    - an application server. This could be fairly complex; for a Python Flask service, this might include a System for an NGINX frontend (which could include the NGINX process, a valid SSL certificate, and that NGINX is responding for the expected domain), another System for UWSGI (which would include the health of both the UWSGI emperor and vassal), the actual python code, presence of any dependencies, 
- Services : These are capabilities that your infrastructure provides. These might be customer-facing, like the actual application; or internal-facing, like a message queue; or parts of your development infrastructure, like the status of build servers.

One key feature of Alpacalert is consuming Services through Sensors. This allows an infrastructure team to report on a failure in the message queue, and the application team to know that their service isn't working but not because of one of their changes.

Alpacalert encourages separating different capabilities as Services and carefully specifying what Services they depend
on. A reporting system might have
- a frontend UI 
- which communicates with a backend Task Generation backend
- which enqueues tasks in a queue
- which are run by the Report Generation application
- which stores them in a filestore 
- which are served up by the Reports Viewing backend 
- which can be viewed through the frontend UI 

Alpacalert makes it easy to separate report generation from report viewing. Configuring report viewing to depend only on the filestore, the Reports Viewing backend, and the frontend allows a service page to indicate that these are still up even if the task queue is down. Alpacalert encourages further separation of capabilities. If the UI is down, report generation is still functional through the API; automated reports can still be created. If the Report Generation application is malfunctioning, report viewing is still functional and requests are still accepted although might be delayed.

Alpacalert has 2 more components:
- Visualisers : These present a service for consumption by machines or humans. For example: printing the status to console; presenting the status on a status webpage; or exposing the status as JSON for consumption by other Alpacalert instances
- Instrumentors : These convert an external system into Sensors, Systems, and Services. For example: transforming Grafana dashboards into Services with alerts as their Sensors; creating a System for a virtual machine with Sensors checking for available memory, CPU, and disk space; or transforming Kubernetes objects into Systems based on their dependent resources.

## Design guidelines

### Using the Registry

alpacalert provides extensibility through the InstrumentorRegistry. This maps an object's kind to the instrumentors that should generate sensors for it. In general, extensions will provide these kinds, and users can add their own sensors to these. For example, a Kubernetes backend might check that PVC has a valid storage class and that it is bound; a user could also add a Prometheus query to ensure that the PVC is less than 80% full.

#### Registering new Kinds

Registry Kinds have 2 components: a namespace and a name. The namespace groups objects from the same domain. For example, "kubernetes.io" for Kubernetes or "grafana.org" for Grafana. The namespace should be a domain name. The name should be a valid URI path for objects that can be instrumented on their own. It may contain a fragment for resources that cannot be instrumented on their own, and must be subresources. For example, a Kubernetes Pod can be pulled with `kubectl get pod/my-pod"; it could have the name "Pod". A volume on a Pod cannot be pulled directly with kubectl and must be pulled as part of the Pod; it could have the name "Pod#volume".

#### Use the Registry for instrumenting subresources

In general, you should use the registry to instrument subresources (resources your resource depends on) instead of calling the instrumentor directly. For the PVC example above, prefer
```python
self.registry.instrument(Instrumentor.Req(Instrumentor.Kind("kubernetes.io", "StorageClass"), storage_class_ref))
```
instead of
```python
SensorStorageclass(self.registry, self.k8s, storage_class)
```

### Instrumenting external systems

For an example, we will use an Instrumentor that converts Grafana alerts into Scanners. Each alert will become a Sensor, and each Dashboard will become a Service with its alerts grouped into a System.

The simplest form of an Instrumentor uses the generic primitives to assemble their Scanners. We would get all Grafana alerts and group them by dashboard. We would then create a `SensorConstant` for each alert, gather them into a `SystemAll`, and create a `ServiceBasic` to expose that. The advantage is that this is simple to write and doesn't require much machinery. The disadvantage is that this doesn't offer a way to instrument only portions of the Grafana alerts. For example, we might want to include some of these alerts in another System; or we might want to only transform some alerts.

For a bit more effort, we can make wrap the generic Scanners with ones for the primitives in our domain. We would create classes `SensorGrafanaAlert` and `SystemGrafanaDashboard`.  Our instrumentor would then create these objects instead of generic ones. Although this doesn't change the logic flow, it can help with keeping track of metadata.

Having these special Scanners allows us to push more logic into them. We can have `SystemGrafanaDashboard` identify which `SensorGrafanaAlert` apply to it; and we can have `SensorGrafanaAlert` query Grafana for their status. Grafana alerts are more efficiently fetched all at once, so fetching them once and having the sensors query that result would maintain performance. The advantage of this approach is that it is now easy for other Systems to reference Grafana dashboards or alerts. For example, it would be easy for a Service for MyWebApp to include the Grafana dashboards for the application server, the DB, and more by specifying just `SystemAll(name="my-web-app", scanners=[SystemGrafanaDashboard("my-web-app"), SystemGrafanaDashboard("my-web-app-db"), ...])`. This allows users to bundle their Grafana dashboards with their other Alpacalert scanners.

## Example Usage

The `examples` subtree has several examples which detail usage. They detail specific end-to-end scenarios, but hopefully
are clear enough that you can cobble together your scenario from them.
