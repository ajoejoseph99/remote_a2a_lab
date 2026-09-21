"""Itinerary Planner specialist agent for attire advice and packing."""

from google.adk.agents.llm_agent import Agent

# Specialist agent that plans what clothes to wear and reminds about umbrellas
itinerary_planner = Agent(
    name="itinerary_planner",
    model="gemini-3.8-flash",
    description="Specialist agent that recommends outfits and packing checklists based on weather conditions, always reminding to carry an umbrella if rain is forecast.",
    instruction="""You are an expert clothing stylist and packing advisor.
When given weather conditions (temperature, sky condition, rain probability) for a destination:
1. Suggest practical and stylish clothing (tops, bottoms, footwear, outerwear).
2. CRITICAL RULE: If the weather report indicates ANY precipitation (such as rain, showers, drizzle, or thunderstorm):
   - You MUST prominently remind the user to carry an umbrella and wear water-resistant footwear.
   - Highlight the umbrella reminder clearly so they do not miss it.
""",
)

# Export as root_agent for standalone discovery
root_agent = itinerary_planner
