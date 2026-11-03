// Title.hpp: the module's own name ("title" in its patch data). Needs jansson only, so tests/title.cpp can reach it.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include <jansson.h>
#include <string>

namespace title {

inline void put (json_t* root, const std::string& t)
{
    json_object_set_new (root, "title", json_stringn (t.data(), t.size()));   // invalid UTF-8: no key, the patch still saves
}

// true when root carries a string "title"
inline bool get (json_t* root, std::string& t)
{
    json_t* j = json_object_get (root, "title");
    if (! j || ! json_is_string (j)) return false;
    t.assign (json_string_value (j), json_string_length (j));
    return true;
}

// root holds nothing but the title: a live rename (vcvrack_set_module_state with data {"title": ...}) that must leave
// the folder, slots and DECK alone
inline bool only (json_t* root) { return json_object_size (root) == 1 && json_object_get (root, "title"); }

inline std::string upper (std::string s)   // ASCII only: UTF-8 bytes pass through
{
    for (char& c : s)
        if (c >= 'a' && c <= 'z') c = (char) (c - 'a' + 'A');
    return s;
}

}
