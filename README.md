[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)

Django Political-Administrative Division of Chile

División Política-Administrativa de Chile para Django

=================================================

``Regiones - Provincias - Comunas``
=================================================

This fork was created to update the package to work with the latest versions of Django 3.2+ (4.1 included) and Python, as the [original developer](https://github.com/jupitercl/django-dpa-chile) appears to be inactive.

Information obtained from the official source of the Government of Chile:
**Geoportal IDE Chile / SUBDERE — División Política Administrativa 2023**

https://geoportal.cl/geoportal/catalog/36391

The data (16 regiones, 56 provincias, 345 comunas) is bundled in the package as
``d3_dpa_chile/data/dpa_chile.json``, so ``populate_dpa_chile`` works offline.
Note: the official layer does not include a polygon for the Antártica comuna
(12202), hence 345 comunas instead of 346. ``lat``/``lng`` are the centroids
of the official polygons (GCS SIRGAS-Chile, WGS84 compatible).

The old API ``https://apis.digital.gob.cl/dpa`` was discontinued (domain no
longer resolves), which is why the data source changed.

Pypi
====

https://pypi.org/project/django3-dpa-chile/

Installation
------------

Install **django3-dpa-chile** using **pip**


    pip install django3-dpa-chile

Add **d3_dpa_chile** to **INSTALLED_APPS**

settings.py
-----------

    # ...

    INSTALLED_APPS =[
    ...
    'd3_dpa_chile',
    ]

    # ...

Populate
--------

    python manage.py migrate d3_dpa_chile

    python manage.py populate_dpa_chile

Optional: load the data from another URL serving a JSON with the same
schema as the bundled data file

    python manage.py populate_dpa_chile --source https://example.com/dpa_chile.json

Updating the bundled data (maintainers only)
--------------------------------------------

Download the official shapefiles and regenerate ``dpa_chile.json``

    pip install pyshp requests

    python scripts/generate_dpa_data.py

Options: ``--zip <path>`` to use an already downloaded zip,
``--url <URL>`` to override the official download URL.

Use
---

    from d3_dpa_chile.models import Region, Provincia, Comuna
