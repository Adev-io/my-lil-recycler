// title.cpp: the "title" key of src/Title.hpp through jansson and back. Needs jansson, so it is not part of make test
// (the core checks build with no Rack); run on Windows with: pwsh -File tools/mk.ps1 title-test
// Author: Ari Klopfer / A_Development. MIT
#include "check.h"
#include "../src/Title.hpp"
#include <cstdlib>

int main()
{
    const std::string name = "Doobie Fool \xC3\xA9";   // UTF-8 survives
    json_t* out = json_object();
    title::put (out, name);
    json_object_set_new (out, "folder", json_string ("C:/crate"));
    char* text = json_dumps (out, 0);
    json_t* in = json_loads (text, 0, nullptr);
    std::string back;
    check (in && title::get (in, back) && back == name, "title: put -> dumps -> loads -> get keeps the name");
    check (in && ! title::only (in), "title: with folder beside it, not a title-only update");
    std::free (text);
    json_decref (out);
    json_decref (in);

    json_t* rename = json_loads ("{\"title\": \"tee time\"}", 0, nullptr);
    check (rename && title::only (rename) && title::get (rename, back) && back == "tee time", "title: {title} alone is a live rename");
    json_decref (rename);

    json_t* old = json_loads ("{\"folder\": \"x\", \"title\": 3}", 0, nullptr);
    back = "kept";
    check (old && ! title::get (old, back) && back == "kept", "title: a non-string title is ignored");
    json_decref (old);

    check (title::upper ("doobie fool \xC3\xA9") == "DOOBIE FOOL \xC3\xA9", "title: upper case, ASCII only");
    std::printf ("%s: %d failure(s)\n", failures ? "FAILED" : "passed", failures);
    return failures;
}
