# schema2reql
Converts json schema into a reql expression

This is kind of a proof of concept, it doesn't support all of json schema, and the resulting reql queries are incredibly huge an inefficient

## How to use it it:

```
$ python3 schema2reql.py test.json
```

You can also import it directly, and use the validator object returned by validate:

```py
my_reql_validator = lambda v: validate(schema, title='root')(v)
```
