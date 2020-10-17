Documentation
*************

https://packaging.python.org/guides/distributing-packages-using-setuptools/

Upload package to PyPi
**********************

. bin/activate

pip install --upgrade pip
pip install wheel
pip install twine

python setup.py sdist
python setup.py bdist_wheel
git commit ...

twine upload dist/*

Test pip package locally
************************

rm -r ping-geo-inst/
mkdir ping-geo-inst/
python3 -m venv ping-geo-inst/

cd ping-geo-inst/
. bin/activate
pip install --upgrade pip
pip install wheel
pip install ../ping-geo/
which ping-geo
ping-geo xxx
