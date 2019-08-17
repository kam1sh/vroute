
python:
	# TODO
	#	error Poetry not found. Install it at https://github.com/sdispater/poetry#installation \
	#	 ! Do not install it via pip as it changes cleo version!
	#
	poetry build

rpm: python
	# https://fpm.readthedocs.io/en/latest/installing.html )
	version="$(vroute --version | cut -d' ' -f 4)"
	fpm.ruby2.5 -s virtualenv -t rpm --name vroute --prefix /usr/share/networkservant dist/networkservant-$version-py3-none-any.whl
