#!/usr/bonsaitools/bin/perl -w
# -*- Mode: perl; indent-tabs-mode: nil -*-
#
# The contents of this file are subject to the Mozilla Public
# License Version 1.1 (the "License"); you may not use this file
# except in compliance with the License. You may obtain a copy of
# the License at http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS
# IS" basis, WITHOUT WARRANTY OF ANY KIND, either express or
# implied. See the License for the specific language governing
# rights and limitations under the License.
#
# The Original Code is the Bugzilla Bug Tracking System.
#
# The Initial Developer of the Original Code is Netscape Communications
# Corporation. Portions created by Netscape are
# Copyright (C) 1998 Netscape Communications Corporation. All
# Rights Reserved.
#
# Contributor(s): Terry Weissman <terry@mozilla.org>
#                 David Gardiner <david.gardiner@unisa.edu.au>

use diagnostics;
use strict;

require "CGI.pl";

$::CheckOptionValues = 0;       # It's OK if we have some bogus things in the
                                # pop-up lists here, from a remembered query
                                # that is no longer quite valid.  We don't
                                # want to crap out in the query page.

# Shut up misguided -w warnings about "used only once":

use vars
  @::CheckOptionValues,
  @::legal_resolution,
  @::legal_bug_status,
  @::legal_components,
  @::legal_keywords,
  @::legal_opsys,
  @::legal_platform,
  @::legal_priority,
  @::legal_product,
  @::legal_severity,
  @::legal_target_milestone,
  @::legal_versions,
  @::log_columns,
  %::versions,
  %::components,
  %::FORM;


if (defined $::FORM{"GoAheadAndLogIn"}) {
    # We got here from a login page, probably from relogin.cgi.  We better
    # make sure the password is legit.
    confirm_login();
} else {
    quietly_check_login();
}
my $userid = 0;
if (defined $::COOKIE{"Bugzilla_login"}) {
    $userid = DBNameToIdAndCheck($::COOKIE{"Bugzilla_login"});
}

# Backwards compatability hack -- if there are any of the old QUERY_*
# cookies around, and we are logged in, then move them into the database
# and nuke the cookie.
if ($userid) {
    my @oldquerycookies;
    foreach my $i (keys %::COOKIE) {
        if ($i =~ /^QUERY_(.*)$/) {
            push(@oldquerycookies, [$1, $i, $::COOKIE{$i}]);
        }
    }
    if (defined $::COOKIE{'DEFAULTQUERY'}) {
        push(@oldquerycookies, [$::defaultqueryname, 'DEFAULTQUERY',
                                $::COOKIE{'DEFAULTQUERY'}]);
    }
    if (@oldquerycookies) {
        foreach my $ref (@oldquerycookies) {
            my ($name, $cookiename, $value) = (@$ref);
            if ($value) {
                my $qname = SqlQuote($name);
                SendSQL("SELECT query FROM namedqueries " .
                        "WHERE userid = $userid AND name = $qname");
                my $query = FetchOneColumn();
                if (!$query) {
                    SendSQL("REPLACE INTO namedqueries " .
                            "(userid, name, query) VALUES " .
                            "($userid, $qname, " . SqlQuote($value) . ")");
                }
            }
            print "Set-Cookie: $cookiename= ; path=/ ; expires=Sun, 30-Jun-1980 00:00:00 GMT\n";
        }
    }
}
                



if ($::FORM{'nukedefaultquery'}) {
    if ($userid) {
        SendSQL("DELETE FROM namedqueries " .
                "WHERE userid = $userid AND name = '$::defaultqueryname'");
    }
    $::buffer = "";
}


my $userdefaultquery;
if ($userid) {
    SendSQL("SELECT query FROM namedqueries " .
            "WHERE userid = $userid AND name = '$::defaultqueryname'");
    $userdefaultquery = FetchOneColumn();
}

my %default;
my %type;

sub ProcessFormStuff {
    my ($buf) = (@_);
    my $foundone = 0;
    foreach my $name ("bug_status", "resolution", "assigned_to",
                      "rep_platform", "priority", "bug_severity",
                      "product", "reporter", "op_sys",
                      "component", "version", "chfield", "chfieldfrom",
                      "chfieldto", "chfieldvalue",
                      "email1", "emailtype1", "emailreporter1",
                      "emailassigned_to1", "emailcc1", "emailqa_contact1",
                      "emaillongdesc1",
                      "email2", "emailtype2", "emailreporter2",
                      "emailassigned_to2", "emailcc2", "emailqa_contact2",
                      "emaillongdesc2",
                      "changedin", "votes", "short_desc", "short_desc_type",
                      "long_desc", "long_desc_type", "bug_file_loc",
                      "bug_file_loc_type", "status_whiteboard",
                      "status_whiteboard_type", "keywords", "bug_id",
                      "bugidtype") {
        $default{$name} = "";
        $type{$name} = 0;
    }


    foreach my $item (split(/\&/, $buf)) {
        my @el = split(/=/, $item);
        my $name = $el[0];
        my $value;
        if ($#el > 0) {
            $value = url_decode($el[1]);
        } else {
            $value = "";
        }
        if (defined $default{$name}) {
            $foundone = 1;
            if ($default{$name} ne "") {
                $default{$name} .= "|$value";
                $type{$name} = 1;
            } else {
                $default{$name} = $value;
            }
        }
    }
    return $foundone;
}


if (!ProcessFormStuff($::buffer)) {
    # Ah-hah, there was no form stuff specified.  Do it again with the
    # default query.
    if ($userdefaultquery) {
        ProcessFormStuff($userdefaultquery);
    } else {
        ProcessFormStuff(Param("defaultquery"));
    }
}


                 

if ($default{'chfieldto'} eq "") {
    $default{'chfieldto'} = "Now";
}



print "Set-Cookie: BUGLIST=
Content-type: text/html\n\n";

GetVersionTable();

sub GenerateEmailInput {
    my ($id) = (@_);
    my $defstr = value_quote($default{"email$id"});
    my $deftype = $default{"emailtype$id"};
    if ($deftype eq "") {
        $deftype = "substring";
    }
    my $assignedto = ($default{"emailassigned_to$id"} eq "1") ? "checked" : "";
    my $reporter = ($default{"emailreporter$id"} eq "1") ? "checked" : "";
    my $cc = ($default{"emailcc$id"} eq "1") ? "checked" : "";
    my $longdesc = ($default{"emaillongdesc$id"} eq "1") ? "checked" : "";

    my $qapart = "";
    my $qacontact = "";
    if (Param("useqacontact")) {
        $qacontact = ($default{"emailqa_contact$id"} eq "1") ? "checked" : "";
        $qapart = qq|
<tr>
<td></td>
<td>
<input type="checkbox" name="emailqa_contact$id" value=1 $qacontact>QA Contact
</td>
</tr>
|;
    }
    if ($assignedto eq "" && $reporter eq "" && $cc eq "" &&
          $qacontact eq "") {
        if ($id eq "1") {
            $assignedto = "checked";
        } else {
            $reporter = "checked";
        }
    }


    return qq|
<table border=1 cellspacing=0 cellpadding=0>
<tr><td>
<table cellspacing=0 cellpadding=0>
<tr>
<td rowspan=2 valign=top><a href="helpemailquery.html">Email:</a>
<input name="email$id" size="30" value="$defstr">&nbsp;matching as
<SELECT NAME=emailtype$id>
<OPTION VALUE="regexp">regexp
<OPTION VALUE="notregexp">not regexp
<OPTION SELECTED VALUE="substring">substring
<OPTION VALUE="exact">exact
</SELECT>
</td>
<td>
<input type="checkbox" name="emailassigned_to$id" value=1 $assignedto>Assigned To
</td>
</tr>
<tr>
<td>
<input type="checkbox" name="emailreporter$id" value=1 $reporter>Reporter
</td>
</tr>$qapart
<tr>
<td align=right>(Will match any of the selected fields)</td>
<td>
<input type="checkbox" name="emailcc$id" value=1 $cc>CC
</td>
</tr>
<tr>
<td></td>
<td>
<input type="checkbox" name="emaillongdesc$id" value=1 $longdesc>Added comment
</td>
</tr>
</table>
</table>
|;
}


            


my $emailinput1 = GenerateEmailInput(1);
my $emailinput2 = GenerateEmailInput(2);


# javascript
    
my $jscript = << 'ENDSCRIPT';
<script language="Javascript1.2" type="text/javascript">
<!--
function array_push(str)
{
   this[this.length] = str;
   return this;
}
Array.prototype.push = array_push;

var cpts = new Array();
var vers = new Array();
var agt=navigator.userAgent.toLowerCase();
ENDSCRIPT


my $p;
my $v;
my $c;
my $i = 0;
my $j = 0;

foreach $c (@::legal_components) {
    $jscript .= "cpts['$c'] = new Array();\n";
}

foreach $v (@::legal_versions) {
    $jscript .= "vers['$v'] = new Array();\n";
}


for $p (@::legal_product) {
    if ($::components{$p}) {
        foreach $c (@{$::components{$p}}) {
            $jscript .= "cpts['$c'].push('$p');\n";
        }
    }

    if ($::versions{$p}) {
        foreach $v (@{$::versions{$p}}) {
            $jscript .= "vers['$v'].push('$p');\n";
        }
    }
}

$i = 0;
$jscript .= q{

// Only display versions/components valid for selected product(s)

function selectProduct(f) {
    var agt=navigator.userAgent.toLowerCase();
    // Netscape 4.04 and 4.05 also choke with an "undefined"
    // error.  if someone can figure out how to "define" the
    // whatever, we'll remove this hack.  in the mean time, we'll
    // assume that v4.00-4.03 also die, so we'll disable the neat
    // javascript stuff for Netscape 4.05 and earlier.
    var agtver = parseFloat(navigator.appVersion);
    if (agtver <= 4.05 ) return;

    var cnt = 0;
    var i;
    var j;
    for (i=0 ; i<f.product.length ; i++) {
        if (f.product[i].selected) {
            cnt++;
        }
    }
    var doall = (cnt == f.product.length || cnt == 0);

    var csel = new Array();
    for (i=0 ; i<f.component.length ; i++) {
        if (f.component[i].selected) {
            csel[f.component[i].value] = 1;
        }
    }

    f.component.options.length = 0;

    for (c in cpts) {
        var doit = doall;
        for (i=0 ; !doit && i<f.product.length ; i++) {
            if (f.product[i].selected) {
                var p = f.product[i].value;
                for (j in cpts[c]) {
                    var p2 = cpts[c][j];
                    if (p2 == p) {
                        doit = true;
                        break;
                    }
                }
            }
        }
        if (doit) {
            var l = f.component.length;
            f.component[l] = new Option(c, c);
            if (csel[c]) {
                f.component[l].selected = true;
            }
        }
    }

    var vsel = new Array();
    for (i=0 ; i<f.version.length ; i++) {
        if (f.version[i].selected) {
            vsel[f.version[i].value] = 1;
        }
    }

    f.version.options.length = 0;

    for (v in vers) {
        var doit = doall;
        for (i=0 ; !doit && i<f.product.length ; i++) {
            if (f.product[i].selected) {
                var p = f.product[i].value;
                for (j in vers[v]) {
                    var p2 = vers[v][j];
                    if (p2 == p) {
                        doit = true;
                        break;
                    }
                }
            }
        }
        if (doit) {
            var l = f.version.length;
            f.version[l] = new Option(v, v);
            if (vsel[v]) {
                f.version[l].selected = true;
            }
        }
    }




}
// -->
</script>

};



# Muck the "legal product" list so that the default one is always first (and
# is therefore visibly selected.

# Commented out, until we actually have enough products for this to matter.

# set w [lsearch $legal_product $default{"product"}]
# if {$w >= 0} {
#    set legal_product [concat $default{"product"} [lreplace $legal_product $w $w]]
# }

PutHeader("Bugzilla Query Page", "Query", "This page lets you search the database for recorded bugs.",
          q{onLoad="selectProduct(document.forms[0]);"});

push @::legal_resolution, "---"; # Oy, what a hack.
push @::legal_target_milestone, "---"; # Oy, what a hack.

print $jscript;

my @logfields = ("[Bug creation]", @::log_columns);

print qq{
<FORM METHOD=GET ACTION="buglist.cgi">

<table>
<tr>
<th align=left><A HREF="bug_status.html">Status</a>:</th>
<th align=left><A HREF="bug_status.html">Resolution</a>:</th>
<th align=left><A HREF="bug_status.html#rep_platform">Platform</a>:</th>
<th align=left><A HREF="bug_status.html#op_sys">OpSys</a>:</th>
<th align=left><A HREF="bug_status.html#priority">Priority</a>:</th>
<th align=left><A HREF="bug_status.html#severity">Severity</a>:</th>
};

print "
</tr>
<tr>
<td align=left valign=top>

@{[make_selection_widget(\"bug_status\",\@::legal_bug_status,$default{'bug_status'}, $type{'bug_status'}, 1)]}

</td>
<td align=left valign=top>
@{[make_selection_widget(\"resolution\",\@::legal_resolution,$default{'resolution'}, $type{'resolution'}, 1)]}

</td>
<td align=left valign=top>
@{[make_selection_widget(\"platform\",\@::legal_platform,$default{'platform'}, $type{'platform'}, 1)]}

</td>
<td align=left valign=top>
@{[make_selection_widget(\"op_sys\",\@::legal_opsys,$default{'op_sys'}, $type{'op_sys'}, 1)]}

</td>
<td align=left valign=top>
@{[make_selection_widget(\"priority\",\@::legal_priority,$default{'priority'}, $type{'priority'}, 1)]}

</td>
<td align=left valign=top>
@{[make_selection_widget(\"bug_severity\",\@::legal_severity,$default{'bug_severity'}, $type{'bug_severity'}, 1)]}

</tr>
</table>

<p>

<table>
<tr><td colspan=2>
$emailinput1<p>
</td></tr><tr><td colspan=2>
$emailinput2<p>
</td></tr>";

my $inclselected = "SELECTED";
my $exclselected = "";

    
if ($default{'bugidtype'} eq "exclude") {
    $inclselected = "";
    $exclselected = "SELECTED";
}
my $bug_id = value_quote($default{'bug_id'}); 

print qq{
<TR>
<TD COLSPAN="3">
<SELECT NAME="bugidtype">
<OPTION VALUE="include" $inclselected>Only
<OPTION VALUE="exclude" $exclselected>Exclude
</SELECT>
bugs numbered: 
<INPUT TYPE="text" NAME="bug_id" VALUE="$bug_id" SIZE=30>
</TD>
</TR>
};

print "
<tr>
<td>
Changed in the <NOBR>last <INPUT NAME=changedin SIZE=2 VALUE=\"$default{'changedin'}\"> days.</NOBR>
</td>
<td align=right>
At <NOBR>least <INPUT NAME=votes SIZE=3 VALUE=\"$default{'votes'}\"> votes.</NOBR>
</tr>
</table>


<table>
<tr>
<td rowspan=2 align=right>Where the field(s)
</td><td rowspan=2>
<SELECT NAME=\"chfield\" MULTIPLE SIZE=4>
@{[make_options(\@logfields, $default{'chfield'}, $type{'chfield'})]}
</SELECT>
</td><td rowspan=2>
changed.
</td><td>
<nobr>dates <INPUT NAME=chfieldfrom SIZE=10 VALUE=\"$default{'chfieldfrom'}\"></nobr>
<nobr>to <INPUT NAME=chfieldto SIZE=10 VALUE=\"$default{'chfieldto'}\"></nobr>
</td>
</tr>
<tr>
<td>changed to value <nobr><INPUT NAME=chfieldvalue SIZE=10> (optional)</nobr>
</td>
</table>


<P>

<table>
<tr>
<TH ALIGN=LEFT VALIGN=BOTTOM>Program:</th>
<TH ALIGN=LEFT VALIGN=BOTTOM>Version:</th>
<TH ALIGN=LEFT VALIGN=BOTTOM><A HREF=describecomponents.cgi>Component:</a></th>
";

if (Param("usetargetmilestone")) {
    print "<TH ALIGN=LEFT VALIGN=BOTTOM>Target Milestone:</th>";
}

print "
</tr>
<tr>

<td align=left valign=top>
<SELECT NAME=\"product\" MULTIPLE SIZE=5 onChange=\"selectProduct(this.form);\">
@{[make_options(\@::legal_product, $default{'product'}, $type{'product'})]}
</SELECT>
</td>

<td align=left valign=top>
<SELECT NAME=\"version\" MULTIPLE SIZE=5>
@{[make_options(\@::legal_versions, $default{'version'}, $type{'version'})]}
</SELECT>
</td>

<td align=left valign=top>
<SELECT NAME=\"component\" MULTIPLE SIZE=5>
@{[make_options(\@::legal_components, $default{'component'}, $type{'component'})]}
</SELECT>
</td>";

if (Param("usetargetmilestone")) {
    print "
<td align=left valign=top>
<SELECT NAME=\"target_milestone\" MULTIPLE SIZE=5>
@{[make_options(\@::legal_target_milestone, $default{'target_milestone'}, $type{'target_milestone'})]}
</SELECT>
</td>";
}


sub StringSearch {
    my ($desc, $name) = (@_);
    my $type = $name . "_type";
    my $def = value_quote($default{$name});
    print qq{<tr>
<td align=right>$desc:</td>
<td><input name=$name size=30 value="$def"></td>
<td><SELECT NAME=$type>
};
    if ($default{$type} eq "") {
        $default{$type} = "substring";
    }
    foreach my $i (["substring", "case-insensitive substring"],
                   ["casesubstring", "case-sensitive substring"],
                   ["allwords", "all words"],
                   ["anywords", "any words"],
                   ["regexp", "regular expression"],
                   ["notregexp", "not ( regular expression )"]) {
        my ($n, $d) = (@$i);
        my $sel = "";
        if ($default{$type} eq $n) {
            $sel = " SELECTED";
        }
        print qq{<OPTION VALUE="$n"$sel>$d\n};
    }
    print "</SELECT></TD>
</tr>
";
}

print "
</tr>
</table>

<table border=0>
";

StringSearch("Summary", "short_desc");
StringSearch("A description entry", "long_desc");
StringSearch("URL", "bug_file_loc");

if (Param("usestatuswhiteboard")) {
    StringSearch("Status whiteboard", "status_whiteboard");
}

if (@::legal_keywords) {
    my $def = value_quote($default{'keywords'});
    print qq{
<TR>
<TD ALIGN="right"><A HREF="describekeywords.cgi">Keywords</A>:</TD>
<TD><INPUT NAME="keywords" SIZE=30 VALUE=$def></TD>
<TD><SELECT NAME=keywords_type>
};
    foreach my $i (["or", "Any of the listed keywords set"]) {
                my ($n, $d) = (@$i);
        my $sel = "";
        if ($default{"keywords"} eq $n) {
            $sel = " SELECTED";
        }
        print qq{<OPTION VALUE="$n"$sel>$d\n};
    }
    print qq{</SELECT></TD></TR>};
}

print "
</table>
<p>
";

if (!$userid) {
    print qq{<INPUT TYPE="hidden" NAME="cmdtype" VALUE="doit">};
} else {
    print "
<BR>
<INPUT TYPE=radio NAME=cmdtype VALUE=doit CHECKED> Run this query
<BR>
";

    my @namedqueries;
    if ($userid) {
        SendSQL("SELECT name FROM namedqueries " .
                "WHERE userid = $userid AND name != '$::defaultqueryname' " .
                "ORDER BY name");
        while (MoreSQLData()) {
            push(@namedqueries, FetchOneColumn());
        }
    }
    
    
    
    
    if (@namedqueries) {
        my $namelist = make_options(\@namedqueries);
        print qq{
<table cellspacing=0 cellpadding=0><tr>
<td><INPUT TYPE=radio NAME=cmdtype VALUE=editnamed> Load the remembered query:</td>
<td rowspan=3><select name=namedcmd>$namelist</select>
</tr><tr>
<td><INPUT TYPE=radio NAME=cmdtype VALUE=runnamed> Run the remembered query:</td>
</tr><tr>
<td><INPUT TYPE=radio NAME=cmdtype VALUE=forgetnamed> Forget the remembered query:</td>
</tr></table>};
    }

    print "
<INPUT TYPE=radio NAME=cmdtype VALUE=asdefault> Remember this as the default query
<BR>
<INPUT TYPE=radio NAME=cmdtype VALUE=asnamed> Remember this query, and name it:
<INPUT TYPE=text NAME=newqueryname>
<BR>
"
}

print "
<NOBR><B>Sort By:</B>
<SELECT NAME=\"order\">
";

my $deforder = "'Importance'";
my @orders = ('Bug Number', $deforder, 'Assignee');

if ($::COOKIE{'LASTORDER'}) {
    $deforder = "Reuse same sort as last time";
    unshift(@orders, $deforder);
}

my $defquerytype = $userdefaultquery ? "my" : "the";

print make_options(\@orders, $deforder);
print "</SELECT></NOBR>
<INPUT TYPE=\"submit\" VALUE=\"Submit query\">
<INPUT TYPE=\"reset\" VALUE=\"Reset back to $defquerytype default query\">
";

if ($userdefaultquery) {
    print qq{<BR><A HREF="query.cgi?nukedefaultquery=1">Set my default query back to the system default</A>};
}

print "
</FORM>
<P>Give me a <A HREF=\"help.html\">clue</A> about how to use this form.
<P>
";


if (UserInGroup("tweakparams")) {
    print "<a href=editparams.cgi>Edit Bugzilla operating parameters</a><br>\n";
}
if (UserInGroup("editcomponents")) {
    print "<a href=editproducts.cgi>Edit Bugzilla products and components</a><br>\n";
}
if (UserInGroup("editkeywords")) {
    print "<a href=editkeywords.cgi>Edit Bugzilla keywords</a><br>\n";
}
if ($userid) {
    print "<a href=relogin.cgi>Log in as someone besides <b>$::COOKIE{'Bugzilla_login'}</b></a><br>\n";
}
print "<a href=changepassword.cgi>Change your password or preferences.</a><br>\n";
print "<a href=\"enter_bug.cgi\">Create a new bug.</a><br>\n";
print "<a href=\"createaccount.cgi\">Open a new Bugzilla account</a><br>\n";
print "<a href=\"reports.cgi\">Bug reports</a><br>\n";

PutFooter();
