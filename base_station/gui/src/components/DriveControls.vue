<template>
  <div class="wrap">
    <div class="speed-state">
      <div class="speed-limiter"> 
        <div>
          <span>Speed Limiter: </span>
        </div>
        <div>
          <span>{{ dampenDisplay }}%</span>
        </div>
      </div>
      <div class="current-state">
        <p>Left State: {{ leftState }}</p>
        <p>Right State: {{ rightState }}</p>
      </div>
    </div>
    <div class="config-state">
      <Checkbox ref="controller" v-bind:name="(controller === 1) ? 'Right' : 'Left'" v-on:toggle="updateController($event)"/>
      <p>Configure State:
        <select v-model="driveState">
          <option value='1'>Disarmed</option>
          <option value='2'>Armed</option>
          <option value='3'>Calibrating</option>
        </select>
      </p>
      <button v-on:click='configState()'>Set State</button>
    </div>
  </div>
</template>

<script>
import Checkbox from './Checkbox.vue'
import { mapGetters, mapMutations } from 'vuex'

import '../utils.js'

let interval;

export default {
  data () {
    return {
      dampen: 0,
      leftState: '-',
      rightState: '-',
      controller: 0,
      driveState: 0
    }
  },

  computed: {

    dampenDisplay: function () {
      return (this.dampen * -50 + 50).toFixed(2)
    },

    ...mapGetters('autonomy', {
      autonEnabled: 'autonEnabled'
    }),
  },

  beforeDestroy: function () {
    window.clearInterval(interval);
  },

  methods: {
    configState(){
      const msg = {
        'type':'DriveStateCmd',
        'controller': this.controller,
        'state': parseInt(this.driveState)
      }

      this.$parent.publish('/drive_state_cmd', msg);
    },

    updateController: function (checked) {
      if (checked) {
        this.controller = 1
      } else {
        this.controller = 0
      }
    }
  },

  created: function () {

    const JOYSTICK_CONFIG = {
      'forward_back': 1,
      'left_right': 2,
      'dampen': 3,
      'kill': 4,
      'restart': 5,
      'pan': 4,
      'tilt': 5
    }

    const updateRate = 0.05;
    interval = window.setInterval(() => {
      const gamepads = navigator.getGamepads()
      for (let i = 0; i < 4; i++) {
        const gamepad = gamepads[i]
        if (gamepad) {
          if (gamepad.id.includes('Logitech')) {
            const joystickData = {
              'type': 'Joystick',
              'forward_back': gamepad.axes[JOYSTICK_CONFIG['forward_back']],
              'left_right': gamepad.axes[JOYSTICK_CONFIG['left_right']],
              'dampen': gamepad.axes[JOYSTICK_CONFIG['dampen']],
              'kill': gamepad.buttons[JOYSTICK_CONFIG['kill']]['pressed'],
              'restart': gamepad.buttons[JOYSTICK_CONFIG['restart']]['pressed']
            }
            this.dampen = gamepad.axes[JOYSTICK_CONFIG['dampen']]

            if (!this.autonEnabled) {
              this.$parent.publish('/drive_control', joystickData)
            }
          }
        }
      }
    }, updateRate*1000)

    this.$parent.subscribe('/drive_state_data', (msg) => {
      if (msg.controller === 0) {
        this.leftState = msg.state.toString()
      } else {
        this.rightState = msg.state.toString()
      }
    })
  },

  components: {
    Checkbox
  }
}
</script>

<style scoped>

.wrap {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-areas:"speed-state config-state";
}

.speed-limiter {
  grid-area: speed-limiter;
}

.current-state {
  grid-area: current-state;
}

.config-state {
  grid-area: config-state;
}

</style>
