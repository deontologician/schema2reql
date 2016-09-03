import rethinkdb as r
import json
import sys


META_KEYWORDS = {'title', 'description', 'default'}
VERBOSE = False

schema_to_reql_type = {
    'array': 'ARRAY',
    'boolean': 'BOOL',
    'integer': 'NUMBER',
    'number': 'NUMBER',
    'null': 'NULL',
    'object': 'OBJECT',
    'string': 'STRING',
}


def main(filename):
    with open(filename) as f:
        schema = json.load(f)
    print(str(r.expr(lambda v: validate(schema, title='root')(v))))


def validate(schema, title=''):
    '''Main validation function'''
    return {
        'array': ArrayValidator,
        'boolean': BooleanValidator,
        'integer': IntegerValidator,
        'number': NumericValidator,
        'null': NullValidator,
        'object': ObjectValidator,
        'string': StringValidator,
    }[schema['type']](schema, title)


class Validator:
    def __init__(self, schema, title=''):
        self.schema = schema
        self.title = schema.get('title', title)
        self.query = None

    def to_branch(self, test, error_msg):
        '''Turns a normal test into an ugly but helpful branch/error test'''
        return lambda v: r.branch(
            test(v),
            True,
            r.error(self.title + ' ' + error_msg),
        )

    def add_req(self, test, error_msg):
        '''Adds a requirement to the running tests for this schema'''
        q = test if VERBOSE else self.to_branch(test, error_msg)
        if self.query is None:
            self.query = q
        else:
            pq = self.query
            self.query = lambda v: pq(v) & q(v)

    def __call__(self, v):
        for keyword, arg in self.schema.items():
            if keyword not in META_KEYWORDS:
                if keyword == 'not':
                    keyword = 'not_'
                getattr(self, keyword)(arg)
        return self.query

    # keywords for any instance type

    def enum(self, arg):
        self.add_req(
            lambda v: r.expr(arg).contains(v),
            'must be equal to one of [%s]' % (', '.join(map(repr, arg))),
        )

    def type(self, arg):
        self.add_req(
            lambda v: v.type_of().eq(schema_to_reql_type[arg]),
            'must be of type %s' % (arg,),
        )

    def allOf(self, arg):
        raise NotImplementedError('allOf')

    def anyOf(self, arg):
        raise NotImplementedError('anyOf')

    def oneOf(self, arg):
        raise NotImplementedError('oneOf')

    def not_(self, arg):
        'Tricky! In verbose mode need to pass down info not to raise errors'
        raise NotImplementedError('not')


class StringValidator(Validator):
    def maxLength(self, arg):
        self.add_req(
            lambda v: v.count() <= arg,
            'must have length at most %s' % (arg,),
        )

    def minLength(self, arg):
        self.add_req(
            lambda v: v.count() >= arg,
            'must have length at least %s' % (arg,),
        )

    def pattern(self, arg):
        self.add_req(
            lambda v: v.match(arg),
            'must match the regex "%s"' % (arg,),
        )


class NullValidator(Validator):
    '''The default type_of check does everything'''


class BooleanValidator(Validator):
    '''The default typeof check does everything'''


class NumericValidator(Validator):
    def multipleOf(self, arg):
        self.add_req(
            lambda v: v.mod(arg).eq(0),
            'must be a multiple of %s' % (arg,),
        )

    def maximum(self, arg):
        self.add_req(
            lambda v: v < arg,
            'must be less than %s' % (arg,),
        )

    def minimum(self, arg):
        self.add_req(
            lambda v: v > arg,
            'must be greater than %s' % (arg,),
        )

    def exclusiveMaximum(self, arg):
        'Essentially a flag for maximum'
        raise NotImplementedError('exclusiveMaximum')

    def exclusiveMinimum(self, arg):
        'A flag for minimum, not a check in its own right'
        raise NotImplementedError('exclusiveMinimum')


class IntegerValidator(NumericValidator):
    def type(self, arg):
        self.add_req(
            lambda v: (v.type_of() == schema_to_reql_type[arg]) &
                      (v.coerce_to('string').split('.').count() == 1),
            'must be an integer',
        )


class ObjectValidator(Validator):
    def maxProperties(self, arg):
        self.add_req(
            lambda obj: obj.count() <= arg,
            'must not have more than %s properties' % (arg,),
        )

    def minProperties(self, arg):
        self.add_req(
            lambda obj: obj.count() >= arg,
            'must have at least %s properties' % (arg,),
        )

    def required(self, arg):
        self.add_req(
            lambda v: v.has_fields(arg),
            'must have the required fields: %s' % (','.join(arg),),
        )

    def properties(self, arg):
        def prop_check(v):
            q = None
            for prop, prop_schema in arg.items():
                new_title = self.title + ' ' + prop
                q_new = r.branch(
                    v.has_fields(prop),
                    validate(prop_schema, new_title)(v[prop]),
                    True,
                )
                q = q_new if q is None else q & q_new
            return q
        self.add_req(prop_check, 'properties must validate')

    def patternProperties(self, arg):
        raise NotImplementedError('patternProperties')

    def dependencies(self, arg):
        raise NotImplementedError('dependencies')

    def additionalProperties(self, arg):
        raise NotImplementedError('additionalProperties')


class ArrayValidator(Validator):

    def items(self, arg):
        'This should really be implemented...'
        raise NotImplementedError('items')

    def additionalItems(self, arg):
        raise NotImplementedError('additionalItems')

    def maxItems(self, arg):
        self.add_req(
            lambda v: v.count() <= arg,
            'must have at most %s items' % (arg,),
        )

    def minItems(self, arg):
        self.add_req(
            lambda v: v.count() >= arg,
            'must have at least %s items' % (arg,),
        )

    def uniqueItems(self, arg):
        raise NotImplementedError('uniqueItems')


if __name__ == '__main__':
    main(sys.argv[1])
