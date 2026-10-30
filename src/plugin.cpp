// plugin.cpp: registers the module.
// Author: Ari Klopfer / A_Development. MIT
#include "plugin.hpp"
Plugin* pluginInstance;
void init (Plugin* p) { pluginInstance = p; p->addModel (modelRecycler); }
