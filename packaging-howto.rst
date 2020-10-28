Documentation
*************

https://packaging.python.org/guides/distributing-packages-using-setuptools/

Update version
**************

.. code-block:: bash

    vi ping_geo/__init__.py

Test pip package locally
************************

.. code-block:: bash

    rm -r ping-geo-inst/
    mkdir ping-geo-inst/
    python3 -m venv ping-geo-inst/

    cd ping-geo-inst/
    . bin/activate
    pip install --upgrade pip
    pip install --upgrade wheel
    pip install ../ping-geo/
    which ping-geo
    ping-geo xxx

Upload package to PyPi
**********************

.. code-block:: bash

    . bin/activate

    pip install --upgrade pip
    pip install --upgrade wheel
    pip install --upgrade twine

    python setup.py sdist
    python setup.py bdist_wheel
    rm -r build/ ping_geo.egg-info/
    git commit ...

    twine upload dist/*

Test pip package from PyPi repo
*******************************

.. code-block:: bash

    rm -r ping-geo-inst/
    mkdir ping-geo-inst/
    python3 -m venv ping-geo-inst/

    cd ping-geo-inst/
    . bin/activate
    pip install ping-geo
    which ping-geo
    ping-geo xxx
