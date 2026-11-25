from django.contrib import admin

from .models import BlockedDestination, Customer, LcrRun, MarginRule, RateSheet

admin.site.register(Customer)
admin.site.register(MarginRule)
admin.site.register(BlockedDestination)
admin.site.register(LcrRun)
admin.site.register(RateSheet)
