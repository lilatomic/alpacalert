# Alpacalert

Alpacalert is a monitoring tool which understands your infrastructure as interacting services. 

## Alpacalert Conceptual Overview

Alpacalert models your infrastructure using 3 primitives: Sensors, Systems, and Services.

- Sensors : These reach out to the world and measure something. That could be the status of a running process, available disk space, or availability of a healthcheck endpoint; for example.
- Systems : These compose Sensors and other Systems into logical units of infrastructure. Systems also make determinations about their health by using data from their Sensors. Some examples of systems:
    - a Virtual Machine with processors, RAM, and disk space. A virtual machine might have limits for the expected RAM or processor usage, or might warn when it is low on disk space.
    - a message queue. A message queue might check that the queue is reachable, that the provided credentials work, and that the expected queues exist.
    - an application server. This could be fairly complex; for a Python Flask service, this might include a System for an NGINX frontend (which could include the NGINX process, a valid SSL certificate, and that NGINX is responding for the expected domain), another System for UWSGI (which would include the health of both the UWSGI emperor and vassal), the actual python code, presence of any dependencies, 
- Services : These are capabilities that your infrastructure provides. These might be customer-facing, like the actual application; or internal-facing, like a message queue; or parts of your development infrastructure, like the status of build servers.

One key feature of Alpacalert is consuming Services through Sensors. This allows an infrastructure team to report on a failure in the message queue, and the application team to know that their service isn't working but not because of one of their changes.

Alpacalert encourages separating different capabilities as Services and carefully specifying what Services they depend
on. A reporting system might have - a frontend UI - which communicates with a backend Task Generation backend - which
enqueues tasks in a queue - which are run by the Report Generation application - which stores them in a filestore -
which are served up by the Reports Viewing backend - which can be viewed through the frontend UI Alpacalert makes it
easy to separate report generation from report viewing. Configuring report viewing to depend only on the filestore, the
Reports Viewing backend, and the frontend allows a service page to indicate that these are still up even if the task
queue is down. Alpacalert encourages further separation of capabilities. If the UI is down, report generation is still
functional through the API; automated reports can still be created. If the Report Generation application is
malfunctioning, report viewing is still functional and requests are still accepted although might be delayed.

## Example Usage

The `examples` subtree has several examples which detail usage. They detail specific end-to-end scenarios, but hopefully
are clear enough that you can cobble together your scenario from them.
