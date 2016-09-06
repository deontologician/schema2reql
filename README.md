# schema2reql
Converts json schema into a reql expression

This is kind of a proof of concept, it doesn't support all of json schema, and the resulting reql queries are incredibly huge an inefficient

## How to use it it:

```
$ python3 schema2reql.py test.json
```

You can also import it directly, and use the validator object returned by validate:

```py
my_reql_validator = validate(schema, title='root').to_reql()
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

You'll get the following reql query as output (I've reformatted for clarity and converted from python to javascript with [multireql](https://github.com/deontologician/multireql))

```js
function(var_1) {
    return (var1.type_of())
        .eq(r.expr('OBJECT'))
        .and(r.branch(var1.has_fields('lastName'), (var1['lastName'].type_of())
                .eq(r.expr('STRING')), true)
            .and(r.branch(var1.has_fields('age'), (var1['age'].type_of())
                .eq(r.expr('NUMBER'))
                .and((var1['age'].floor())
                    .eq(r.expr('integer')))
                .and((var1['age'])
                    .gt(r.expr(0))), true))
            .and(r.branch(var1.has_fields('firstName'), (var1['firstName'].type_of())
                .eq(r.expr('STRING')), true)))
        .and(var1.has_fields(['firstName', 'lastName']))
}
```

Really beautiful stuff
