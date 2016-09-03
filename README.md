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

## What it looks like

Give this example schema:

```json
{
  "title": "Example Schema",
  "type": "object",
  "properties": {
    "firstName": {
      "type": "string"
    },
    "lastName": {
      "type": "string"
    },
    "age": {
      "description": "Age in years",
      "type": "integer",
      "minimum": 0
    }
  },
  "required": ["firstName", "lastName"]
}
```

You'll get the following reql query as out (I've reformatted for clarity):

```python
lambda var_2: ((
    r.branch(var_2.has_fields(['firstName', 'lastName']),
        True,
        r.error('Example Schema must have the required fields: firstName,lastName')) & 
    r.branch(var_2.type_of() == r.expr('OBJECT'),
        True,
        r.error('Example Schema must be of type object'))) & 
    r.branch(((
        r.branch(var_2.has_fields('age'),
            r.branch((var_2 > r.expr(0)), 
                True,
                r.error('Example Schema age must be greater than 0')) & 
            r.branch(((var_2.type_of() == r.expr('NUMBER')) &
                      (var_2.coerce_to('string').split('.').count() == r.expr(1))),
                True,
        # yadda yadda it keeps going
```

Really beautiful stuff
