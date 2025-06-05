from collections.abc import Collection, Iterator
import pathlib
import shutil

import httpx
import rich.progress
from bs4 import BeautifulSoup
import typer


app = typer.Typer()

class NotEnoughFreeDiskSpace(Exception):
    pass

def form_url(
    base_url: str,
    sub_path: pathlib.Path = pathlib.Path(),
    )-> str:
    
    scheme, _, address = base_url.rstrip('/').partition('://')
    return f'{scheme}://{(address / sub_path).as_posix().rstrip('/')}'

def download_file(  
    file_name: pathlib.Path,
    url: str,
    dest: pathlib.Path,
    free_space_buffer:int = 100_000_000,
    already_downloaded_urls: set | None = None,
    ) -> None:

    """ Download file_name from url+file_name to dest / file_name"""

    already_downloaded_urls = already_downloaded_urls or set()

    dest.mkdir(exist_ok=True,parents=True)
    file_download_path = dest / file_name.name

    url = form_url(url, file_name)

    if url in already_downloaded_urls:
        return

    already_downloaded_urls.add(url)

    with httpx.stream("GET", url) as response:
        download_size = int(response.headers["Content-Length"])
                
        free_space = shutil.disk_usage(dest).free - free_space_buffer

        if file_download_path.is_file():
            file_size = file_download_path.stat().st_size
            if file_size >= download_size:
                return
            free_space += file_size
        

        if download_size > free_space:
            raise NotEnoughFreeDiskSpace(
                f'{file_name=}, {download_size=}, {free_space=}, '
                f'{free_space_buffer=}, {url=}'
                )

        file_download_path.unlink(missing_ok=True)

        with file_download_path.open('wb') as downloaded_file:
            for chunk in response.iter_bytes():
                downloaded_file.write(chunk)


class FailedDownloads(ExceptionGroup):
    pass


def download_files(  
    files: Collection[pathlib.Path],
    url: str,
    dest: pathlib.Path,
    free_space_buffer:int = 100_000_000,
    already_downloaded_urls: set | None = None,
    ) -> dict[pathlib.Path,httpx.RequestError | httpx.HTTPStatusError]:

    already_downloaded_urls = already_downloaded_urls or set()

    errors = {}

    with rich.progress.Progress(
        "[progress.percentage]{task.percentage:>3.0f}%",
        rich.progress.SpinnerColumn(),
        rich.progress.BarColumn(bar_width=None),
        rich.progress.MofNCompleteColumn(),
        rich.progress.TimeElapsedColumn(),
        rich.progress.TimeRemainingColumn(),
    ) as progress:
        download_pdfs_task = progress.add_task("Download_files", total = len(files))

        for n, file_path in enumerate(files,1):

            # file_path = file_.strip()

            # if not file_path:
                # continue
                     
            path = pathlib.Path(file_path)

                    
            try:
                download_file(
                    file_name = pathlib.Path(path),
                    url=url,
                    dest=dest,
                    already_downloaded_urls = already_downloaded_urls,
                    )
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                errors[file_path] = e
                pass

            progress.update(download_pdfs_task, completed=n)

    return errors

def find_files_to_download(
    url: str,
    sub_path: pathlib.Path = pathlib.Path(),
    file_exts: Collection[str] = ['.pdf',],
    already_seen_urls: set[str] | None = None,
    ) -> Iterator[pathlib.Path]:
    """ Download all files found at url = contents.  """

    already_seen_urls = already_seen_urls or set()

    url = form_url(url, sub_path)

    if url in already_seen_urls:
        return

    already_seen_urls.add(url)

    response = httpx.get(f'{url}/')
    
    if not response.is_success:
        return

    contents_page_html = response.content

    parsed = BeautifulSoup(contents_page_html, features="html.parser")

    if parsed.body is None or parsed.body.pre is None:
        return



    hrefs = [str(href) 
              for a in parsed.body.pre.find_all('a')
              if hasattr(a,'attrs')
              if (href := a.attrs.get('href'))
              if '?' not in href
              if href not in url
              if '..' not in href
            ]

    for href in hrefs:
        for file_ext in file_exts:
            if href.endswith(file_ext):
                yield sub_path / href
                break # inner loop
        else:
            # Does not end in any ext
            # Treat as sub folder
            if '.' in href:
                continue # outer loop
            yield from find_files_to_download(
                url,
                sub_path / href.strip('/'),
                file_exts,
                already_seen_urls,
                )




@app.command()
def search(
    url: str,
    exts: list[str],
    ):

    for file_name in find_files_to_download(
        url = url,
        file_exts = exts,
        ):
        
        print(file_name.as_posix())


@app.command()
def download(
    url: str,
    dest: pathlib.Path = pathlib.Path('.'),
    files: str = '',
    exts: list[str] = ['.pdf'],
    ):
    if files and pathlib.Path(files).is_file():
        with open(files,'rt') as file_names_file:
            files_to_download = [pathlib.Path(file_) 
                                 for file_name in file_names_file
                                 if (file_ := file_name.strip())
                                ] 
    else:
        files_to_download = list(find_files_to_download(
            url = url,
            file_exts=exts,
            ))

    errors = download_files(files_to_download, url, dest)

    if errors:
        raise FailedDownloads(f'Failed to download: {list(errors)}',list(errors.values()))


if __name__ == '__main__':
    app()