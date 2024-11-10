Information
-----------

This is the source package used to build the offline archive for the
Cppreference C++ standard library reference documentation available at
<http://en.cppreference.com>.

If there is no 'reference/' subdirectory in this package, the actual
documentation is not present here and must be obtained separately in order to
build the binary package. This can be done in two ways:

 1) Downloading a prepared archive from
 <http://en.cppreference.com/w/Cppreference:Archives>. This method is preferred.

 2) Running `make source` which will pull the documentation directly from the
 website page-by-page. You should not normally use this method. The download
 script is updated to take into account any changes of the website only when
 there's new release at <http://en.cppreference.com/w/Cppreference:Archives>.
 If the layout of the website has changed since the last release, the download
 script might not work. Also, it puts unnecessary load on the servers. Please do
 not use this method unless you know what you are doing.

Note, that abovementioned documentation is still a raw copy of the website and
needs to be transformed in order to be suitable for local viewing. Three
documentation formats are currently supported:

 1) Plain html documentation. Can be generated using `make doc_html`. The
 result of the transformation will be placed at the 'output/reference'
 subdirectory.

 2) Devhelp documentation format. Can be generated using `make doc_devhelp`.
 `make install` installs the documentation into proper locations.

 3) QT Help documentation format (.qch). Can be generated using `make doc_qch`.
 `make install` installs the documentation into proper locations.

Simply running `make all` will generate documentation in all three formats.

Running `make release` will generate the release archives which are uploaded
to <http://en.cppreference.com/w/Cppreference:Archives>.

Dependencies
------------

The package depends on 'wget' (>=1.15), 'python3', 'python3-lxml',
and 'qhelpgenerator' for the generation of the documentation.

See also
--------

Debian packaging information for this package is maintained at
<https://github.com/p12tic/cppreference-doc_debian>

About this fork
---------------

I made this fork mainly because the last official version of the offline package
was rather old and much had changed with new C++ versions. Now I try to update
more frequently.

Additional changes from upstream are:

 * Better layout by centering the content on the page.
 * Keeping links between the C and C++ parts of the documentation.
 * Keeping a footer with a link to the online version of each page.
