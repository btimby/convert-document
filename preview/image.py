from wand.image import Image, Color


def preview_image(path, width, height):
    with Image(filename=path, resolution=300) as s:
        d = Image(s.sequence[0])
        d.background_color = Color("white")
        d.alpha_channel = 'remove'
        d.transform(resize='%ix%i>' % (width, height))
        return d.make_blob('png')
