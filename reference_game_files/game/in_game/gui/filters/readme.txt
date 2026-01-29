# Scripted filters for lists of objects.
#
# These appear when a list of objects of a particular type are displayed, allowing some generic filter operations that can be further selected from with the tag label.
#
# For lists with sub-items, if one of the sub-items pass the filter, the entire item pass it. Then we can modifiy the item from code to change it's data or layout, as we do in the building macrobuilder.
#
# For each filter you'll need to add appropriate strings. 
#   search_filter_<tag>_name: filter name
#   search_filter_<tag>_desc: description of the filter
#   search_filter_<tag>_format: for filters that use the range, this shows how to display a number
#
# scope: <scope type> the type of object that can be operated on by this filter
# trigger: <trigger> whether or not the supplied scope object passes the filter
# range: allows the filter to present ranges of values to select from
#    min:
#    max:
#    step:
#    format: <string> used to format the display text
# tag: <string> this tag will be used by each list in .gui files to show only the filters with the tag specified
# group: <integer> for grouping filters in the same UI background.
# exclusive_group: <integer> for using radio buttons in the group, so filters will exclude each other so if you select one, the previous selected will be unselected. MUST BE IN EVERY FILTER IN THE GROUP.
# invert: <yes/no> exclude items by default and include them if checked
# enabled_at_start: <yes/no> initial state of the filter, ticked or not
# group_sorting: for sorting the fitlers in that group, for now there is only alphabetical sorting.