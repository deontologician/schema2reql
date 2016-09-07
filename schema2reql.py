import rethinkdb as r
import json
import sys
from functools import wraps


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
    print(str(r.expr(validate(schema, title='root').to_reql())))


def validate(schema, title=''):
    '''Main validation function'''
    return Validator(schema, title).to_reql()


def propfor(prop_type):
    def _propfor(f):
        @wraps(f)
        def checker(self, arg):
            check = f(self, arg)
            if self.schema.get('type') is None:
                # No type assertion, so emit conditionally with other
                # soft checks dependent on a type
                self.ctx.soft_checks.setdefault(prop_type, []).append(
                    self.ctx.build_check(check))
                return None, None
            elif self.schema.get('type') == prop_type:
                # A type assertion for this type exists, so just emit
                # this check as a normal conjunction
                return check
            else:
                # A type assertion for another type exists, don't emit
                # anything, we can't possibly succeed
                return None, None
        return checker
    return _propfor


def conjunct(checks):
    '''Turns an array of check functions into a single conjunction'''
    return lambda v: r.and_(*map(lambda check: check(v), checks))


class Context:
    def __init__(self, verbose):
        self.verbose = verbose
        self.soft_checks = {}
        self.conjunction = []

    def to_reql(self):
        '''Convert this context to a reql function'''
        # Emit soft checks, bunching together all checks that are
        # conditional on a particular type being asserted
        for soft_type, checks in self.soft_checks.items():
            self.conjunction.append(lambda v: r.branch(
                v.type_of() == schema_to_reql_type[soft_type],
                conjunct(checks)(v),
                True  # if type doesn't match, it's ok
            ))
        return conjunct(self.conjunction)

    def also(self, check):
        '''Adds a requirement to the running tests for this schema'''
        if check[0] is not None:
            self.conjunction.append(self.build_check(check))

    def build_check(self, check):
        test, error_msg = check
        if self.verbose:
            # TODO: check if we're reverse logic to decide whether to
            # demorgan this branch
            return self.to_branch(test, error_msg)
        else:
            return test

    def to_branch(self, test, error_msg):
        '''Turns a normal test into an ugly but helpful branch/error test'''
        return lambda v: r.branch(
            test(v),
            True,
            r.error(self.title + ' ' + error_msg),
        )


class Validator:
    def __init__(self, schema, title='', verbose=False):
        self.schema = schema
        self.title = schema.get('title', title)
        self.ctx = None
        self.verbose = False

    def to_reql(self):
        self.ctx = Context(self.verbose)
        if 'type' in self.schema:
            self.ctx.also(self.type(self.schema['type']))
        for keyword, spec in self.schema.items():
            if keyword in ('type', 'description', 'title'):
                continue  # already handled
            if keyword == 'not':
                keyword = 'not_'  # python keyword collision!
            try:
                self.ctx.also(getattr(self, keyword)(self.schema[keyword]))
            except AttributeError as ae:
                raise NotImplementedError(keyword)
        return self.ctx.to_reql()

    def default(self, arg):
        '''No-op'''
        return None, None

    def type(self, arg):
        def type_check(v):
            def type_to_reql(t):
                check = v.type_of() == schema_to_reql_type[t]
                if t == 'integer':
                    # Add additional check for integers
                    check = check & (v.floor() == v)
                return check

            if isinstance(arg, list):
                check = r.or_(*map(type_to_reql, arg))
            else:
                check = type_to_reql(arg)
            return check

        return (type_check, 'type must be %s' % (arg,))

    # keywords for any instance type

    def enum(self, arg):
        return (
            lambda v: r.expr(arg).contains(v),
            'must be equal to one of [%s]' % (', '.join(map(repr, arg))),
        )

    # def allOf(self, arg):
    #     raise NotImplementedError('allOf')

    # def anyOf(self, arg):
    #     raise NotImplementedError('anyOf')

    # def oneOf(self, arg):
    #     raise NotImplementedError('oneOf')

    # def not_(self, arg):
    #     'Tricky! In verbose mode need to pass down info not to raise errors'
    #     raise NotImplementedError('not')

    @propfor('string')
    def maxLength(self, arg):
        return (
            lambda v: v.count() <= arg,
            'must have length at most %s' % (arg,),
        )

    @propfor('string')
    def minLength(self, arg):
        return (
            lambda v: v.count() >= arg,
            'must have length at least %s' % (arg,),
        )

    @propfor('string')
    def pattern(self, arg):
        return (
            lambda v: v.match(arg),
            'must match the regex "%s"' % (arg,),
        )

    @propfor('number')
    def multipleOf(self, arg):
        # You'd think we could do a mod here, but it has to work for
        # floats too apparently. So we check if dividing results in a
        # whole number instead
        return (
            lambda v: r.do(v.div(arg), lambda r: r.floor() == r),
            'must be a multiple of %s' % (arg,),
        )

    @propfor('number')
    def maximum(self, arg):
        if self.schema.get('exclusiveMaximum') is True:
            return (
                lambda v: v < arg,
                'must be less than %s' % (arg,),
            )
        else:
            return (
                lambda v: v <= arg,
                'must be at most than %s' % (arg,),
            )

    @propfor('number')
    def minimum(self, arg):
        if self.schema.get('exclusiveMinimum') is True:
            return (
                lambda v: v > arg,
                'must be greater than %s' % (arg,),
            )
        else:
            return (
                lambda v: v >= arg,
                'must be at least %s' % (arg,),
            )

    def exclusiveMaximum(self, arg):
        'A flag for maximum'
        return None, None  # no-op

    def exclusiveMinimum(self, arg):
        'A flag for minimum'
        return None, None  # no-op

    @propfor('object')
    def maxProperties(self, arg):
        return (
            lambda obj: obj.count() <= arg,
            'must not have more than %s properties' % (arg,),
        )

    @propfor('object')
    def minProperties(self, arg):
        return (
            lambda obj: obj.count() >= arg,
            'must have at least %s properties' % (arg,),
        )

    @propfor('object')
    def required(self, arg):
        return (
            lambda v: v.has_fields(arg),
            'must have the required fields: %s' % (','.join(arg),),
        )

    @propfor('object')
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
        return (prop_check, 'properties must validate')

    # @propfor('object')
    # def patternProperties(self, arg):
    #     raise NotImplementedError('patternProperties')

    # @propfor('object')
    # def dependencies(self, arg):
    #     raise NotImplementedError('dependencies')

    # @propfor('object')
    # def additionalProperties(self, arg):
    #     raise NotImplementedError('additionalProperties')

    # @propfor('array')
    # def items(self, arg):
    #     'This should really be implemented...'
    #     raise NotImplementedError('items')

    # @propfor('array')
    # def additionalItems(self, arg):
    #     raise NotImplementedError('additionalItems')

    @propfor('array')
    def maxItems(self, arg):
        return (
            lambda v: v.count() <= arg,
            'must have at most %s items' % (arg,),
        )

    @propfor('array')
    def minItems(self, arg):
        return (
            lambda v: v.count() >= arg,
            'must have at least %s items' % (arg,),
        )

    # @propfor('array')
    # def uniqueItems(self, arg):
    #     raise NotImplementedError('uniqueItems')

    def ref(self, arg):
        return None, None

    def __getattr__(self, name):
        if name == '$ref':
            return self.ref
        else:
            raise NotImplementedError(name)



if __name__ == '__main__':
    main(sys.argv[1])
