# Download_files
## Usage 
### One liner

```uvx download_files download https://www.example.com .jpg .png```


### With review step

```uvx download_files search https://www.example.com .jpg .png > files.txt```

```uvx download_files download https://www.example.com --files files.txt```


## Overview
Download_files parses the anchor elements in an html page (`<a/>` elements).  If 
another folder is found in the `href`, the link is followed and any page found is 
parsed recursively.  If the last part of the href matches a specified file extension,
it is printed, for piping to the download list (if using `search`) or downloaded later.

No special efforts are made to circumvent rate limits.  The code does not
magically allow files to be downloaded, that you do not already have 
permission to download some other way.