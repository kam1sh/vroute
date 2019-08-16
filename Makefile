python:
	poetry build

rpm: python
	version="$(netservant --version | cut -d' ' -f 4)"
	# https://fpm.readthedocs.io/en/latest/installing.html
	fpm.ruby2.5 -s virtualenv -t rpm --name networkservant --prefix /usr/share/networkservant dist/networkservant-$version-py3-none-any.whl
