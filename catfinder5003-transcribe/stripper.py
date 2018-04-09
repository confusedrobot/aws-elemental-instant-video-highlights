def strip (data):
    if any ([isinstance(data, type) for type in [dict, list, str, unicode]]):
        return len(data) == 0
    return False
def stripper (data):
    if isinstance(data, dict):
        newdata = {k: stripper(v) for k, v in data.iteritems()}
        return {k: v for k, v in newdata.iteritems() if not strip(v)}
    elif isinstance(data, list):
        newdata = [stripper(v) for v in data]
        return [v for v in newdata if not strip(v)]
    return data
data = {u'items': [], u'sample' : u'data', u'samplelist' : [u'list',u'list2'], u'sampledict' : { u'value' : u'item1'}, u'transcripts': [{u'transcript': u''}]}
# data = {u'items': [], u'transcripts': [{u'transcript': u''}]}
blah = stripper(data)
print('blah: {}'.format(blah))