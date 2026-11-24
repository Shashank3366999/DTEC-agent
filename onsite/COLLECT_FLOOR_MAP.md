# Measure the floor (about 20 minutes, one person)

The robot can only be as right as this map. We need **spots** and the **straight walks** between them.

1. **Pick map north.** Stand where the robot will start, facing the way it will face. That direction is north (`heading 0`). Start is `x 0, y 0`. Forward is `+y`, right is `+x`. (`y` and `x` are in metres.)
2. **Walk to every place**: meeting room, conference room, each of the four call booths, team tables, kitchen. Count steps; one normal step is about 0.7 m. The spot is where the robot should **stop**, in front of the place.
3. **Add a spot at every corner** where the robot must turn. Give it a name the operator will recognise without help ("the glass door", "the plant"). No name like "junction 2".
4. **Note the straight walks** between neighbouring spots (no wall or table in between, wide enough for the robot).
5. **Note which side each place is on** (`faces`): standing at the spot, which direction is the place? 0 = north, 90 = east (right), 180 = south, 270 = west.
6. Photo of each spot and a sketch. No faces.

```
Spot:            x:      y:      faces:      named by:
Straight walks:  start - ___ , ___ - ___
```

Then in `sdk/profiles/dtec_floor.json`:

- `floor.nodes`: the spots. Corners need a `name`; places get theirs from `places`.
- `floor.edges`: the straight walks, two spot ids each.
- `places[].node` and `places[].faces`.
- Delete `"demo": true` from `floor` when it is real.

Check: `cd sdk && python3 -m oasis_voice validate && python3 -m oasis_voice routes`, then `export` and walk it with `/walk`.

Straight walks matter more than exact metres: turns come from the angles, stops come from the landmarks.

**Also ask:** where does the robot start each route, can we stick paper markers up, which mic, what is the wake word, may we have OpenCV in the container.
